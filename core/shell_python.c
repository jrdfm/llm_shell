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

/*
 * Python method: shell.execute(command)
 * Executes a single shell command
 * Converts Python string → C string, calls C function, converts result back to Python
 */
static PyObject *
Shell_execute(ShellObject *self, PyObject *args)
{
    const char *command;
    // Parse Python arguments into C variables
    // "s" format means expect a string and convert to char*
    if (!PyArg_ParseTuple(args, "s", &command))
        return NULL;

    // Call our C implementation
    int result = shell_execute(self->ctx, command);
    
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
 * Python method: shell.execute_pipeline([cmd1, cmd2, ...])
 * Executes a pipeline of shell commands
 * Converts Python list of strings → C array of strings, executes, returns result
 */
static PyObject *
Shell_execute_pipeline(ShellObject *self, PyObject *args)
{
    PyObject *commands_list;
    // Parse Python argument into PyObject (should be a list)
    if (!PyArg_ParseTuple(args, "O", &commands_list))
        return NULL;

    // Verify we got a Python list
    if (!PyList_Check(commands_list)) {
        PyErr_SetString(PyExc_TypeError, "Argument must be a list of strings");
        return NULL;
    }

    // Get list size and allocate C array
    Py_ssize_t num_commands = PyList_Size(commands_list);
    const char **commands = malloc(sizeof(char *) * num_commands);
    
    // Convert each Python string to C string
    for (Py_ssize_t i = 0; i < num_commands; i++) {
        PyObject *item = PyList_GetItem(commands_list, i);
        if (!PyUnicode_Check(item)) {
            free(commands);
            PyErr_SetString(PyExc_TypeError, "List items must be strings");
            return NULL;
        }
        // PyUnicode_AsUTF8 converts Python string to UTF-8 C string
        commands[i] = PyUnicode_AsUTF8(item);
    }

    // Call C implementation
    int result = shell_execute_pipeline(self->ctx, commands, num_commands);
    free(commands);

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
     "Execute a shell command"},
    {"execute_pipeline", (PyCFunction) Shell_execute_pipeline, METH_VARARGS,
     "Execute a pipeline of shell commands"},
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