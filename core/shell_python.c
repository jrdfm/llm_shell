#define PY_SSIZE_T_CLEAN  // Must be defined before including Python.h for clean Py_ssize_t definition
#include <Python.h>
#include "shell.h"

/* 
 * Define the Python object structure
 * This creates a new type that Python can work with
 * PyObject_HEAD is a macro that contains the basic Python object header
 * ctx is our custom C shell context that we want to access from Python
 */
typedef struct {
    PyObject_HEAD
    ShellContext *ctx;  // Pointer to our C shell implementation context
} ShellObject;

/*
 * Destructor for our Shell object
 * Called by Python's garbage collector when object is no longer referenced
 * Responsible for cleaning up both Python object and our C resources
 */
static void
Shell_dealloc(ShellObject *self)
{
    if (self->ctx) {
        shell_cleanup(self->ctx);  // Clean up our C shell context
    }
    Py_TYPE(self)->tp_free((PyObject *) self);  // Free the Python object itself
}

/*
 * Constructor for our Shell object
 * Called when Python code creates a new Shell() instance
 * Allocates and initializes both Python object and C shell context
 */
static PyObject *
Shell_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    ShellObject *self;
    // Allocate the Python object first
    self = (ShellObject *) type->tp_alloc(type, 0);
    if (self != NULL) {
        // Initialize our C shell context
        self->ctx = shell_init();
        if (self->ctx == NULL) {
            Py_DECREF(self);  // Clean up Python object if C init fails
            return NULL;
        }
    }
    return (PyObject *) self;
}

// Helper function to convert a Python list of strings to char** argv
// Returns allocated argv (caller must free it and its contents) or NULL on failure
static char** py_list_to_argv(PyObject* py_list) {
    if (!PyList_Check(py_list)) {
        PyErr_SetString(PyExc_TypeError, "Argument must be a list of strings");
        return NULL;
    }

    Py_ssize_t argc = PyList_Size(py_list);
    // Allocate space for char* pointers plus the terminating NULL
    char **argv = malloc(sizeof(char*) * (argc + 1));
    if (!argv) {
        PyErr_NoMemory();
        return NULL;
    }

    for (Py_ssize_t i = 0; i < argc; i++) {
        PyObject *item = PyList_GetItem(py_list, i);
        if (!PyUnicode_Check(item)) {
            PyErr_SetString(PyExc_TypeError, "List items must be strings");
            // Free already allocated strings and the argv array
            for (Py_ssize_t j = 0; j < i; j++) {
                free(argv[j]);
            }
            free(argv);
            return NULL;
        }
        // PyUnicode_AsUTF8 returns a pointer to the internal buffer, which is
        // generally okay for short-lived usage like passing to execvp.
        // If the C function stored these pointers long-term, we'd need strdup.
        // However, let's use strdup for safety, as C layer might evolve.
        const char *utf8_str = PyUnicode_AsUTF8(item);
        if (!utf8_str) { // Error during conversion
             for (Py_ssize_t j = 0; j < i; j++) {
                free(argv[j]);
            }
            free(argv);
            return NULL; // Error already set by PyUnicode_AsUTF8
        }
        argv[i] = strdup(utf8_str);
        if (!argv[i]) { // strdup failed
            PyErr_NoMemory();
            for (Py_ssize_t j = 0; j < i; j++) {
                free(argv[j]);
            }
            free(argv);
            return NULL;
        }
    }
    argv[argc] = NULL; // Null-terminate the array
    return argv;
}

// Helper function to free argv created by py_list_to_argv
static void free_argv(char **argv) {
    if (!argv) return;
    for (int i = 0; argv[i] != NULL; i++) {
        free(argv[i]);
    }
    free(argv);
}

/*
 * Python method: shell.execute(argv_list)
 * Executes a single shell command given a list of arguments.
 */
static PyObject *
Shell_execute(ShellObject *self, PyObject *args)
{
    PyObject *py_argv_list;
    // Parse argument as a Python list object
    if (!PyArg_ParseTuple(args, "O!", &PyList_Type, &py_argv_list))
        return NULL; // Error message already set by PyArg_ParseTuple

    // Convert Python list to C argv
    char **argv = py_list_to_argv(py_argv_list);
    if (!argv) {
        return NULL; // Error message set by py_list_to_argv
    }

    // Call our C implementation with the parsed argv
    int result = shell_execute(self->ctx, argv);

    // Free the argv array and its contents
    free_argv(argv);

    // Get error message if command failed
    const char *error = shell_get_error(self->ctx);
    if (result != 0 && error != NULL) {
        // Return tuple (exit_code, error_message)
        return Py_BuildValue("(is)", result, error);
    }

    // Return just exit code if no error
    return Py_BuildValue("(iO)", result, Py_None);
}

/*
 * Python method: shell.execute_pipeline([ [cmd1_arg0, cmd1_arg1], [cmd2_arg0], ... ])
 * Executes a pipeline of shell commands, taking lists of arguments for each.
 */
static PyObject *
Shell_execute_pipeline(ShellObject *self, PyObject *args)
{
    PyObject *py_pipeline_list;
    // Parse argument as a Python list object
    if (!PyArg_ParseTuple(args, "O!", &PyList_Type, &py_pipeline_list))
        return NULL;

    Py_ssize_t num_commands = PyList_Size(py_pipeline_list);
    if (num_commands == 0) {
        return Py_BuildValue("(iO)", 0, Py_None); // Empty pipeline is success (like shell)
    }

    // Allocate the array of argv arrays (char***)
    // Need space for num_commands pointers to (char**)
    char ***pipeline_argv = malloc(sizeof(char**) * num_commands);
    if (!pipeline_argv) {
        PyErr_NoMemory();
        return NULL;
    }
    // Initialize all pointers to NULL in case of early exit during allocation
    for(Py_ssize_t k=0; k < num_commands; ++k) {
        pipeline_argv[k] = NULL;
    }

    // Convert each inner list
    Py_ssize_t i;
    for (i = 0; i < num_commands; i++) {
        PyObject *py_inner_list = PyList_GetItem(py_pipeline_list, i);
        // Check if the inner item is actually a list before converting
        if (!PyList_Check(py_inner_list)) {
             PyErr_SetString(PyExc_TypeError, "Pipeline argument must be a list of lists of strings");
             // Cleanup already allocated inner lists
             for (Py_ssize_t j = 0; j < i; j++) {
                 free_argv(pipeline_argv[j]);
             }
             free(pipeline_argv);
             return NULL;
        }
        pipeline_argv[i] = py_list_to_argv(py_inner_list); // Reuse helper
        if (!pipeline_argv[i]) {
            // Error occurred in conversion, cleanup previously converted lists
            // Note: pipeline_argv[i] is already NULL from py_list_to_argv failure
            for (Py_ssize_t j = 0; j < num_commands; j++) { // Free all up to num_commands
                 if(pipeline_argv[j]) free_argv(pipeline_argv[j]);
            }
            free(pipeline_argv);
            return NULL; // Error already set by py_list_to_argv
        }
    }

    // Call C implementation with the array of argv arrays
    // Note: We cast away constness here, which is generally safe if the C
    // function doesn't modify the strings, but technically invokes UB if it did.
    // The C function signature uses `char *const *const *` for clarity.
    int result = shell_execute_pipeline(self->ctx, (char *const *const *)pipeline_argv, num_commands);

    // Free the allocated pipeline structure
    for (i = 0; i < num_commands; i++) {
        // Check pointer before freeing, in case of earlier error
        if(pipeline_argv[i]) {
           free_argv(pipeline_argv[i]);
        }
    }
    free(pipeline_argv);

    // Get error message if pipeline failed
    const char *error = shell_get_error(self->ctx);
    if (result != 0 && error != NULL) {
        // Return tuple (exit_code, error_message)
        return Py_BuildValue("(is)", result, error);
    }
    // Return just exit code if no error
    return Py_BuildValue("(iO)", result, Py_None);
}

/*
 * Python method: shell.cd(path)
 * Changes current directory
 * Converts Python string path → C string, updates shell context
 */
static PyObject *
Shell_cd(ShellObject *self, PyObject *args)
{
    const char *path;
    if (!PyArg_ParseTuple(args, "s", &path))
        return NULL;

    int result = shell_cd(self->ctx, path);
    return PyLong_FromLong(result);
}

/*
 * Python method: shell.getenv(name)
 * Gets environment variable value
 * Returns None if variable doesn't exist
 */
static PyObject *
Shell_getenv(ShellObject *self, PyObject *args)
{
    const char *name;
    if (!PyArg_ParseTuple(args, "s", &name))
        return NULL;

    const char *value = shell_getenv(self->ctx, name);
    if (value == NULL) {
        Py_RETURN_NONE;  // Python's None if variable not found
    }
    return PyUnicode_FromString(value);  // Convert C string to Python string
}

/*
 * Python method: shell.setenv(name, value)
 * Sets environment variable
 * Takes two Python strings, converts to C strings
 */
static PyObject *
Shell_setenv(ShellObject *self, PyObject *args)
{
    const char *name;
    const char *value;
    // "ss" format means parse two strings
    if (!PyArg_ParseTuple(args, "ss", &name, &value))
        return NULL;

    int result = shell_setenv(self->ctx, name, value);
    return PyLong_FromLong(result);
}

/*
 * Python method: shell.get_cwd()
 * Gets current working directory
 * No arguments, returns Python string
 */
static PyObject *
Shell_get_cwd(ShellObject *self, PyObject *Py_UNUSED(ignored))
{
    return PyUnicode_FromString(self->ctx->cwd);
}

/*
 * Method table mapping Python method names to C functions
 * Each entry specifies:
 * - Python method name
 * - C function to call
 * - Flags for argument parsing
 * - Method documentation
 */
static PyMethodDef Shell_methods[] = {
    {"execute", (PyCFunction) Shell_execute, METH_VARARGS,
     "Execute a shell command given a list of arguments"},
    {"execute_pipeline", (PyCFunction) Shell_execute_pipeline, METH_VARARGS,
     "Execute a pipeline of commands given list of lists of arguments"},
    {"cd", (PyCFunction) Shell_cd, METH_VARARGS,
     "Change current directory"},
    {"getenv", (PyCFunction) Shell_getenv, METH_VARARGS,
     "Get environment variable"},
    {"setenv", (PyCFunction) Shell_setenv, METH_VARARGS,
     "Set environment variable"},
    {"get_cwd", (PyCFunction) Shell_get_cwd, METH_NOARGS,
     "Get current working directory"},
    {NULL}  /* Sentinel marking end of method list */
};

/*
 * Python type object defining our Shell class
 * Specifies all the operations that can be performed on Shell objects
 */
static PyTypeObject ShellType = {
    PyVarObject_HEAD_INIT(NULL, 0)  // Required macro for all Python types
    .tp_name = "core.Shell",        // Module.Class name
    .tp_doc = "Shell object",       // Class documentation
    .tp_basicsize = sizeof(ShellObject),  // Size of our object
    .tp_itemsize = 0,              // Size of variable part (if any)
    .tp_flags = Py_TPFLAGS_DEFAULT,  // Standard features
    .tp_new = Shell_new,           // Constructor
    .tp_dealloc = (destructor) Shell_dealloc,  // Destructor
    .tp_methods = Shell_methods,    // Method table
};

/*
 * Module definition structure
 * Defines the module that will contain our Shell class
 */
static struct PyModuleDef moduledef = {
    PyModuleDef_HEAD_INIT,    // Required macro for all modules
    "core",                   // Module name
    "Shell core module.",     // Module documentation
    -1,                      // Module keeps state in global variables
    NULL                     // No module-level methods
};

/*
 * Module initialization function
 * Called when Python imports our module
 * Sets up the module and the Shell type
 */
PyMODINIT_FUNC
PyInit_core(void)
{
    PyObject *m;

    // Finalize the type object including inherited slots
    if (PyType_Ready(&ShellType) < 0)
        return NULL;

    // Create the module
    m = PyModule_Create(&moduledef);
    if (m == NULL)
        return NULL;

    // Add our type to the module
    Py_INCREF(&ShellType);
    if (PyModule_AddObject(m, "Shell", (PyObject *) &ShellType) < 0) {
        Py_DECREF(&ShellType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
} 