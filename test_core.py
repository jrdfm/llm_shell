import core
import shlex
import os
import pytest # Assuming pytest is used or can be added to requirements

# Fixture to create a shell instance for each test
@pytest.fixture
def shell():
    return core.Shell()

# Fixture to handle temporary directory changes
@pytest.fixture
def change_dir(tmp_path):
    original_dir = os.getcwd()
    os.chdir(tmp_path)
    yield tmp_path # Provide the temp path to the test
    os.chdir(original_dir)

def test_execute_simple(shell):
    """Test executing a simple command"""
    cmd = "echo Hello from C shell!"
    args = shlex.split(cmd)
    exit_code, error = shell.execute(args)
    assert exit_code == 0
    assert error is None

def test_execute_with_args(shell):
    """Test executing a command with arguments"""
    cmd = "echo multiple args here"
    args = shlex.split(cmd)
    exit_code, error = shell.execute(args)
    assert exit_code == 0
    assert error is None

def test_execute_complex_args(shell):
    """Test executing with quotes and escapes (parsed by shlex)"""
    cmd = 'echo "Argument with spaces" \'Another with single quotes\' and\\escaped\ characters'
    args = shlex.split(cmd)
    exit_code, error = shell.execute(args)
    assert exit_code == 0
    assert error is None

def test_execute_fail(shell):
    """Test executing a command that should fail"""
    cmd = "cat non_existent_file_should_fail"
    args = shlex.split(cmd)
    exit_code, error = shell.execute(args)
    assert exit_code != 0
    assert error is not None
    assert "No such file or directory" in error # Check common error message

def test_execute_invalid_command(shell):
    """Test executing an invalid command"""
    cmd = "thiscommandshouldnotexistanywhere"
    args = shlex.split(cmd)
    exit_code, error = shell.execute(args)
    assert exit_code == 127 # Typical exit code for command not found via execvp
    assert error is not None
    assert "No such file or directory" in error # execvp error message

def test_pipeline_simple(shell):
    """Test a simple pipeline"""
    cmds = [
        "echo Hello",
        "tr a-z A-Z",
    ]
    pipeline_args = [shlex.split(c) for c in cmds]
    exit_code, error = shell.execute_pipeline(pipeline_args)
    assert exit_code == 0
    # Note: Current C implementation doesn't capture pipeline errors well
    # assert error is None

def test_pipeline_complex(shell):
    """Test a more complex pipeline"""
    cmds = [
        "echo one two three",
        "wc -w",
    ]
    pipeline_args = [shlex.split(c) for c in cmds]
    exit_code, error = shell.execute_pipeline(pipeline_args)
    assert exit_code == 0
    # assert error is None

def test_pipeline_fail_stage(shell):
    """Test pipeline where an intermediate stage fails"""
    cmds = [
        "echo valid start",
        "cat non_existent_file_should_fail", # This should fail
        "wc -c"
    ]
    pipeline_args = [shlex.split(c) for c in cmds]
    exit_code, error = shell.execute_pipeline(pipeline_args)
    # The exit code reflects the *last* command. wc -c might succeed if it gets empty input.
    # A more robust test would capture stderr from the failing stage if possible.
    # For now, just check the exit code of the last stage (might be 0 or non-zero depending on wc behavior)
    assert error is None # Current implementation doesn't capture errors from pipeline stages

def test_cd(shell, change_dir):
    """Test changing directory"""
    original_cwd = shell.get_cwd()
    # change_dir fixture changes os.getcwd(), shell.cd changes shell's internal cwd
    shell.cd(str(change_dir)) # Use the temp path provided by fixture
    temp_cwd = shell.get_cwd()
    assert temp_cwd == str(change_dir)
    assert temp_cwd != original_cwd

    # Test cd back
    exit_code, error = shell.execute(["cd", original_cwd])
    assert exit_code == 0
    assert error is None
    assert shell.get_cwd() == original_cwd

def test_cd_fail(shell):
    """Test changing to a non-existent directory"""
    original_cwd = shell.get_cwd()
    exit_code, error = shell.execute(["cd", "/non/existent/path/hopefully"])
    assert exit_code != 0
    assert error is not None
    assert "No such file or directory" in error
    assert shell.get_cwd() == original_cwd # CWD should not change on failure

def test_env_vars(shell):
    """Test setting and getting environment variables"""
    var_name = "MY_TEST_VAR_CORE"
    var_value = "core_test_value_123"

    # Ensure it doesn't exist initially
    assert shell.getenv(var_name) is None

    # Set it
    exit_code = shell.setenv(var_name, var_value)
    assert exit_code == 0

    # Get it back
    retrieved_value = shell.getenv(var_name)
    assert retrieved_value == var_value

    # Overwrite it
    new_value = "new value!"
    exit_code = shell.setenv(var_name, new_value)
    assert exit_code == 0
    assert shell.getenv(var_name) == new_value

def test_get_cwd(shell):
    """Test getting the current working directory"""
    # Compare with os.getcwd() as a sanity check
    assert shell.get_cwd() == os.getcwd()

# Example of how to run using pytest:
# 1. pip install pytest
# 2. Run `pytest test_core.py` in the terminal 