class Student(object):
    def __init__(self, name, score):
        self.__name = name
        self.__score = score

    def __str__(self):
        return 'Student object (name: %s, score: %d)' % (self.__name, self.__score)

    __repr__ = __str__

