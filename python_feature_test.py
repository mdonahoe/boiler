import unittest
from typing import List, Dict
from collections import namedtuple
from functools import wraps
from contextlib import contextmanager


class PythonFeatureTests(unittest.TestCase):
    """Unit tests for 50 different Python features"""

    def test_01_integers(self):
        """Test integer arithmetic"""
        result = 10 + 5
        self.assertEqual(result, 15)
        print("01. Integer arithmetic: 10 + 5 = 15")

    def test_02_floats(self):
        """Test float operations"""
        result = 3.14 * 2
        self.assertAlmostEqual(result, 6.28)
        print("02. Float operations: 3.14 * 2 = 6.28")

    def test_03_strings(self):
        """Test string concatenation"""
        result = "Hello" + " " + "World"
        self.assertEqual(result, "Hello World")
        print("03. String concatenation: 'Hello' + ' World' = 'Hello World'")

    def test_04_f_strings(self):
        """Test f-string formatting"""
        name = "Python"
        result = f"Hello {name}!"
        self.assertEqual(result, "Hello Python!")
        print("04. F-string formatting: f'Hello {name}!' = 'Hello Python!'")

    def test_05_lists(self):
        """Test list operations"""
        lst = [1, 2, 3]
        lst.append(4)
        self.assertEqual(lst, [1, 2, 3, 4])
        print("05. List operations: [1,2,3].append(4) = [1,2,3,4]")

    def test_06_list_comprehension(self):
        """Test list comprehension"""
        result = [x * 2 for x in range(5)]
        self.assertEqual(result, [0, 2, 4, 6, 8])
        print("06. List comprehension: [x*2 for x in range(5)] = [0,2,4,6,8]")

    def test_07_dictionaries(self):
        """Test dictionary operations"""
        d = {"a": 1, "b": 2}
        d["c"] = 3
        self.assertEqual(d["c"], 3)
        print("07. Dictionary operations: dict['c'] = 3")

    def test_08_dict_comprehension(self):
        """Test dictionary comprehension"""
        result = {x: x**2 for x in range(3)}
        self.assertEqual(result, {0: 0, 1: 1, 2: 4})
        print("08. Dict comprehension: {x: x**2 for x in range(3)} = {0:0, 1:1, 2:4}")

    def test_09_sets(self):
        """Test set operations"""
        s1 = {1, 2, 3}
        s2 = {3, 4, 5}
        result = s1 & s2
        self.assertEqual(result, {3})
        print("09. Set intersection: {1,2,3} & {3,4,5} = {3}")

    def test_10_tuples(self):
        """Test tuple immutability"""
        t = (1, 2, 3)
        self.assertEqual(len(t), 3)
        print("10. Tuple operations: len((1,2,3)) = 3")

    def test_11_tuple_unpacking(self):
        """Test tuple unpacking"""
        a, b, c = (1, 2, 3)
        self.assertEqual((a, b, c), (1, 2, 3))
        print("11. Tuple unpacking: a,b,c = (1,2,3)")

    def test_12_lambda_functions(self):
        """Test lambda functions"""
        square = lambda x: x ** 2
        self.assertEqual(square(5), 25)
        print("12. Lambda function: (lambda x: x**2)(5) = 25")

    def test_13_map_function(self):
        """Test map function"""
        result = list(map(lambda x: x * 2, [1, 2, 3]))
        self.assertEqual(result, [2, 4, 6])
        print("13. Map function: map(lambda x: x*2, [1,2,3]) = [2,4,6]")

    def test_14_filter_function(self):
        """Test filter function"""
        result = list(filter(lambda x: x % 2 == 0, [1, 2, 3, 4]))
        self.assertEqual(result, [2, 4])
        print("14. Filter function: filter(even, [1,2,3,4]) = [2,4]")

    def test_15_zip_function(self):
        """Test zip function"""
        result = list(zip([1, 2], ['a', 'b']))
        self.assertEqual(result, [(1, 'a'), (2, 'b')])
        print("15. Zip function: zip([1,2], ['a','b']) = [(1,'a'), (2,'b')]")

    def test_16_enumerate_function(self):
        """Test enumerate function"""
        result = list(enumerate(['a', 'b', 'c']))
        self.assertEqual(result, [(0, 'a'), (1, 'b'), (2, 'c')])
        print("16. Enumerate: enumerate(['a','b','c']) = [(0,'a'), (1,'b'), (2,'c')]")

    def test_17_any_function(self):
        """Test any function"""
        result = any([False, True, False])
        self.assertTrue(result)
        print("17. Any function: any([False, True, False]) = True")

    def test_18_all_function(self):
        """Test all function"""
        result = all([True, True, False])
        self.assertFalse(result)
        print("18. All function: all([True, True, False]) = False")

    def test_19_string_slicing(self):
        """Test string slicing"""
        s = "Python"
        result = s[1:4]
        self.assertEqual(result, "yth")
        print("19. String slicing: 'Python'[1:4] = 'yth'")

    def test_20_list_slicing(self):
        """Test list slicing"""
        lst = [1, 2, 3, 4, 5]
        result = lst[::2]
        self.assertEqual(result, [1, 3, 5])
        print("20. List slicing: [1,2,3,4,5][::2] = [1,3,5]")

    def test_21_exception_handling(self):
        """Test exception handling"""
        try:
            result = 10 / 2
            self.assertEqual(result, 5.0)
            print("21. Exception handling: try-except works")
        except ZeroDivisionError:
            self.fail("Should not raise exception")

    def test_22_class_definition(self):
        """Test class definition and instantiation"""
        class Dog:
            def __init__(self, name):
                self.name = name

        dog = Dog("Buddy")
        self.assertEqual(dog.name, "Buddy")
        print("22. Class definition: Dog('Buddy').name = 'Buddy'")

    def test_23_inheritance(self):
        """Test class inheritance"""
        class Animal:
            def speak(self):
                return "Sound"

        class Cat(Animal):
            def speak(self):
                return "Meow"

        cat = Cat()
        self.assertEqual(cat.speak(), "Meow")
        print("23. Inheritance: Cat inherits from Animal")

    def test_24_property_decorator(self):
        """Test property decorator"""
        class Circle:
            def __init__(self, radius):
                self._radius = radius

            @property
            def radius(self):
                return self._radius

        c = Circle(5)
        self.assertEqual(c.radius, 5)
        print("24. Property decorator: @property works")

    def test_25_staticmethod(self):
        """Test staticmethod decorator"""
        class Math:
            @staticmethod
            def add(a, b):
                return a + b

        result = Math.add(3, 4)
        self.assertEqual(result, 7)
        print("25. Static method: Math.add(3,4) = 7")

    def test_26_classmethod(self):
        """Test classmethod decorator"""
        class Counter:
            count = 0

            @classmethod
            def increment(cls):
                cls.count += 1
                return cls.count

        result = Counter.increment()
        self.assertEqual(result, 1)
        print("26. Class method: Counter.increment() = 1")

    def test_27_generator_function(self):
        """Test generator function"""
        def gen():
            yield 1
            yield 2
            yield 3

        result = list(gen())
        self.assertEqual(result, [1, 2, 3])
        print("27. Generator function: list(gen()) = [1,2,3]")

    def test_28_generator_expression(self):
        """Test generator expression"""
        gen = (x ** 2 for x in range(4))
        result = list(gen)
        self.assertEqual(result, [0, 1, 4, 9])
        print("28. Generator expression: (x**2 for x in range(4)) = [0,1,4,9]")

    def test_29_context_manager(self):
        """Test context manager"""
        @contextmanager
        def my_context():
            yield "value"

        with my_context() as val:
            self.assertEqual(val, "value")
        print("29. Context manager: with statement works")

    def test_30_multiple_assignment(self):
        """Test multiple assignment"""
        a = b = c = 10
        self.assertEqual((a, b, c), (10, 10, 10))
        print("30. Multiple assignment: a = b = c = 10")

    def test_31_ternary_operator(self):
        """Test ternary operator"""
        x = 5
        result = "positive" if x > 0 else "non-positive"
        self.assertEqual(result, "positive")
        print("31. Ternary operator: 'positive' if x > 0 else 'non-positive'")

    def test_32_walrus_operator(self):
        """Test walrus operator (assignment expression)"""
        if (n := 10) > 5:
            result = n * 2
        self.assertEqual(result, 20)
        print("32. Walrus operator: (n := 10) assigns and returns")

    def test_33_string_methods(self):
        """Test string methods"""
        s = "  hello  "
        result = s.strip().upper()
        self.assertEqual(result, "HELLO")
        print("33. String methods: '  hello  '.strip().upper() = 'HELLO'")

    def test_34_join_method(self):
        """Test join method"""
        result = "-".join(["a", "b", "c"])
        self.assertEqual(result, "a-b-c")
        print("34. Join method: '-'.join(['a','b','c']) = 'a-b-c'")

    def test_35_split_method(self):
        """Test split method"""
        result = "a,b,c".split(",")
        self.assertEqual(result, ["a", "b", "c"])
        print("35. Split method: 'a,b,c'.split(',') = ['a','b','c']")

    def test_36_isinstance_function(self):
        """Test isinstance function"""
        result = isinstance(5, int)
        self.assertTrue(result)
        print("36. Isinstance: isinstance(5, int) = True")

    def test_37_type_hints(self):
        """Test type hints"""
        def add_numbers(a: int, b: int) -> int:
            return a + b

        result = add_numbers(3, 4)
        self.assertEqual(result, 7)
        print("37. Type hints: function with type annotations works")

    def test_38_named_tuples(self):
        """Test named tuples"""
        Point = namedtuple('Point', ['x', 'y'])
        p = Point(1, 2)
        self.assertEqual(p.x, 1)
        print("38. Named tuples: Point(1,2).x = 1")

    def test_39_decorator_function(self):
        """Test decorator function"""
        def my_decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs) * 2
            return wrapper

        @my_decorator
        def get_five():
            return 5

        result = get_five()
        self.assertEqual(result, 10)
        print("39. Decorator: @my_decorator doubles return value")

    def test_40_args_parameter(self):
        """Test *args parameter"""
        def sum_all(*args):
            return sum(args)

        result = sum_all(1, 2, 3, 4)
        self.assertEqual(result, 10)
        print("40. *args parameter: sum_all(1,2,3,4) = 10")

    def test_41_kwargs_parameter(self):
        """Test **kwargs parameter"""
        def print_kwargs(**kwargs):
            return kwargs

        result = print_kwargs(a=1, b=2)
        self.assertEqual(result, {"a": 1, "b": 2})
        print("41. **kwargs parameter: captures keyword arguments")

    def test_42_magic_methods(self):
        """Test magic methods"""
        class Number:
            def __init__(self, value):
                self.value = value

            def __add__(self, other):
                return Number(self.value + other.value)

        n1 = Number(5)
        n2 = Number(3)
        result = n1 + n2
        self.assertEqual(result.value, 8)
        print("42. Magic methods: __add__ enables + operator")

    def test_43_list_extend(self):
        """Test list extend"""
        lst = [1, 2]
        lst.extend([3, 4])
        self.assertEqual(lst, [1, 2, 3, 4])
        print("43. List extend: [1,2].extend([3,4]) = [1,2,3,4]")

    def test_44_dict_get(self):
        """Test dict get method"""
        d = {"a": 1}
        result = d.get("b", "default")
        self.assertEqual(result, "default")
        print("44. Dict get: d.get('b', 'default') = 'default'")

    def test_45_set_comprehension(self):
        """Test set comprehension"""
        result = {x % 3 for x in range(10)}
        self.assertEqual(result, {0, 1, 2})
        print("45. Set comprehension: {x%3 for x in range(10)} = {0,1,2}")

    def test_46_sorted_function(self):
        """Test sorted function"""
        result = sorted([3, 1, 4, 1, 5])
        self.assertEqual(result, [1, 1, 3, 4, 5])
        print("46. Sorted function: sorted([3,1,4,1,5]) = [1,1,3,4,5]")

    def test_47_reversed_function(self):
        """Test reversed function"""
        result = list(reversed([1, 2, 3]))
        self.assertEqual(result, [3, 2, 1])
        print("47. Reversed function: reversed([1,2,3]) = [3,2,1]")

    def test_48_min_max_functions(self):
        """Test min and max functions"""
        lst = [1, 5, 3, 9, 2]
        self.assertEqual(min(lst), 1)
        self.assertEqual(max(lst), 9)
        print("48. Min/Max functions: min=[1], max=[9] from [1,5,3,9,2]")

    def test_49_sum_function(self):
        """Test sum function"""
        result = sum([1, 2, 3, 4, 5])
        self.assertEqual(result, 15)
        print("49. Sum function: sum([1,2,3,4,5]) = 15")

    def test_50_unpacking_operator(self):
        """Test unpacking operator"""
        list1 = [1, 2]
        list2 = [3, 4]
        result = [*list1, *list2]
        self.assertEqual(result, [1, 2, 3, 4])
        print("50. Unpacking operator: [*[1,2], *[3,4]] = [1,2,3,4]")


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
