def extend_dependencies(method):
    def args_wrapper(*values: str):
        def func_wrapper(*args, **kwargs):
            return method(*args, **kwargs)

        method._depends.extend(values)
        return func_wrapper

    return args_wrapper
