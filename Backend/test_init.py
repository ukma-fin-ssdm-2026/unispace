def test_hello_world():
    expected = "Hello World"
    actual = "Hello " + "World"
    assert expected == actual, "Тест не пройдено!"
    print("Hello World тест успішно пройдено.")

if __name__ == "__main__":
    test_hello_world()