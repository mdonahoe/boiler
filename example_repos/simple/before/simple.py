#! /bin/env python3
# Hello World
import sys
import collections

class Dog:
    pass

class Cat:
    pass

def unused():
    d = collections.defaultdict(int)
    print("this is never called", d)

def main():
    x = Dog()
    print("hello python")
    return 0

if __name__ == "__main__":
    sys.exit(main())
