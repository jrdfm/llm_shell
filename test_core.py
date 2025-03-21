import core

def test_basic_shell():
    shell = core.Shell()
    
    # Test basic command execution
    print("Testing basic command...")
    result = shell.execute("echo Hello from C shell!")
    print(f"Exit code: {result}")
    
    # Test pipeline execution
    print("\nTesting pipeline...")
    result = shell.execute_pipeline([
        "echo Hello",
        "tr a-z A-Z",
        "sed 's/HELLO/GREETINGS/'"
    ])
    print(f"Pipeline exit code: {result}")
    
    # Test directory operations
    print("\nTesting directory operations...")
    print(f"Current directory: {shell.get_cwd()}")
    shell.cd("..")
    print(f"After cd ..: {shell.get_cwd()}")
    shell.cd("-")  # Go back to previous directory
    
    # Test environment variables
    print("\nTesting environment variables...")
    shell.setenv("TEST_VAR", "test_value")
    value = shell.getenv("TEST_VAR")
    print(f"TEST_VAR = {value}")

if __name__ == "__main__":
    test_basic_shell() 