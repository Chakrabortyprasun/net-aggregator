import os


def test_file_assembly_correctness():
    filename = "02_output.bin"
    assert os.path.exists(filename), "The output file was not created."

    actual_size = os.path.getsize(filename)
    assert actual_size == 300, f"Expected 300 bytes, but got {actual_size}"

    with open(filename, "rb") as f:
        data = f.read()

    # httpbin's /range endpoint cycles a→z starting from byte 0 — fully deterministic
    expected = bytes((97 + i % 26) for i in range(300))
    assert data == expected, "Chunk data is corrupted, out of order, or overlapping at a boundary"