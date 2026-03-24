These are my non-negotiable coding style guidelines for Python code in this project. They are designed to ensure that the code is clean, maintainable, and easy to understand. Please adhere to these guidelines when writing or reviewing code for this project.

- Ensure the code is easy to read and understand.
- Use descriptive variable and function names.
- Abstract code into functions and classes where appropriate to improve readability and reusability. Ensure that each function performs a single, well-defined task.
- Bias against try / except blocks. Use them only when necessary.
- Add docstrings / type hints / comments (where appropriate) to clarify the code.
- Bias for using Python 3.13 onwards features, such as pattern matching, dataclasses, and type annotations.
- Bias towards using guard clauses to reduce nesting and improve readability.
- Ensure functions are small and focused on a single task. This allows for easier testing and maintenance.
- Always return one type of value from a function, rather than multiple types. This helps to avoid confusion and makes the code easier to understand.
- Use OOP where possible. This can help to organize code and make it more modular and reusable.
- Bias against list comprehensions. Normal loops are more readable and easier to understand, especially for complex operations. Use list comprehensions only for very simple cases where they enhance readability.
- Avoid using 'object' as a type. Instead, use more specific, inbuilt python types to improve code clarity and maintainability.
- Never define a function within another function. This can lead to confusion and makes the code harder to read and maintain. Always define functions at the top level of a module or class.
- Only do one thing inside a try block. This makes it easier to identify and handle exceptions, and improves code readability. If you need to perform multiple operations that could raise exceptions, consider breaking them into separate try blocks or functions.
- Avoid using try and except blocks to control the flow of the program. Instead, use them only for handling exceptional cases that are not part of the normal flow. This helps to keep the code clean and easier to understand.