import modal

# TODO: Change stub name to a new, unique namespace.
stub = modal.Stub("example-get-started")


@stub.function()
@modal.web_endpoint()
def square(x):
    print("This code is running on a remote worker!")
    return x**2


@stub.local_entrypoint()
def main():
    number = 4
    print(f"The square of {number} is {square.remote(number)}.")
