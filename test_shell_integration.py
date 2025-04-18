# test_shell_integration.py
import pytest
import pytest_asyncio # Import the asyncio fixture decorator
import asyncio
import os
import shlex
from shell import LLMShell # Import the main shell class

# --- Mocking Dependencies (Optional but recommended for isolation) ---
# If LLMClient or ErrorHandler make network calls or have complex state,
# mocking them can make tests faster and more reliable.
# Example using pytest-mock (needs `pip install pytest-mock`):
#
# @pytest.fixture(autouse=True)
# def mock_dependencies(mocker):
#     # Mock the LLM client to avoid real API calls
#     mocker.patch('shell.LLMClient', return_value=mocker.MagicMock())
#     # Mock the error handler's external calls if needed
#     mocker.patch('shell.ErrorHandler.handle_error', new_callable=mocker.AsyncMock)
# --- End Mocking ---


@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture
async def llm_shell(event_loop):
    """Fixture to create an instance of LLMShell for testing."""
    # Temporarily set API key if needed for initialization (or mock LLMClient)
    original_key = os.getenv("GOOGLE_API_KEY")
    if not original_key:
        os.environ["GOOGLE_API_KEY"] = "dummy_key_for_testing"

    shell = LLMShell()
    # Allow initialization potentially involving async operations if any
    # await asyncio.sleep(0) # If __init__ had async parts

    yield shell # Provide the instance to the test

    # Cleanup: Restore original API key env var
    if not original_key:
        del os.environ["GOOGLE_API_KEY"]
    else:
        os.environ["GOOGLE_API_KEY"] = original_key

# Use pytest-asyncio for running async tests
pytestmark = pytest.mark.asyncio

async def test_integration_simple_command(llm_shell, capsys):
    """Test running a simple command through handle_command"""
    await llm_shell.handle_command("echo Integration Test")
    captured = capsys.readouterr()
    # Check stdout - Note: The C core currently doesn't capture/return stdout
    # We only get exit code and stderr. So we can't assert exact stdout here easily.
    # We *can* check that no error was printed to stderr via the handler.
    assert "Integration Test" not in captured.err # Assuming echo doesn't write to stderr
    # We should ideally check the *actual* stdout if the C core returned it.

async def test_integration_complex_args(llm_shell, capsys):
    """Test shlex parsing via handle_command"""
    cmd = 'echo "Spaces and \\"quotes\\" are handled"'
    await llm_shell.handle_command(cmd)
    captured = capsys.readouterr()
    # Again, primarily checking for lack of errors
    assert "Spaces and" not in captured.err

async def test_integration_pipeline(llm_shell, capsys):
    """Test a simple pipeline"""
    cmd = "echo pipeline test | wc -w"
    await llm_shell.handle_command(cmd)
    captured = capsys.readouterr()
    # Cannot easily check exact stdout (e.g., "2") without capturing it from C core.
    # Check for lack of reported errors
    assert "pipeline test" not in captured.err
    assert "wc" not in captured.err

async def test_integration_cd_builtin(llm_shell, tmp_path):
    """Test the cd built-in handling"""
    original_cwd = llm_shell.core_shell.get_cwd()
    cmd = f"cd {tmp_path}"
    await llm_shell.handle_command(cmd)
    assert llm_shell.core_shell.get_cwd() == str(tmp_path)
    # Go back
    await llm_shell.handle_command(f"cd {original_cwd}")
    assert llm_shell.core_shell.get_cwd() == original_cwd

async def test_integration_invalid_command(llm_shell, mocker):
    """Test error handling for an invalid command"""
    # Mock the error handler's output for verification
    mock_error_handle = mocker.patch('shell.ErrorHandler.handle_error', new_callable=mocker.AsyncMock)
    cmd = "invalid_command_xyz"
    await llm_shell.handle_command(cmd)
    # Check that the error handler was called with an appropriate message
    mock_error_handle.assert_awaited_once()
    args, kwargs = mock_error_handle.call_args
    assert "Command failed" in args[0] or "No such file or directory" in args[0]

async def test_integration_shlex_error(llm_shell, mocker):
    """Test error handling for a shlex parsing error"""
    mock_error_handle = mocker.patch('shell.ErrorHandler.handle_error', new_callable=mocker.AsyncMock)
    cmd = "echo 'unterminated quote"
    await llm_shell.handle_command(cmd)
    # Check that the error handler was called with a parsing error
    mock_error_handle.assert_awaited_once()
    args, kwargs = mock_error_handle.call_args
    assert "Parsing error" in args[0]
    assert "No closing quotation" in args[0]

async def test_integration_redirection_as_args(llm_shell, capsys):
    """Test that redirection chars are treated as args (current limitation)"""
    # This test confirms current behavior, NOT desired shell behavior
    cmd = "echo hello > output.txt"
    await llm_shell.handle_command(cmd)
    captured = capsys.readouterr()
    # Check that '>' wasn't interpreted and no error occurred immediately
    # (unless echo itself errors on '>' as an arg)
    assert ">" not in captured.err # crude check
    # Clean up dummy file if echo happens to create it (unlikely)
    if os.path.exists("output.txt"):
        os.remove("output.txt")
