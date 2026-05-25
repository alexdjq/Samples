class Student(object):
    def __init__(self, name, score):
        self.__name = name
        self.__score = score

    def __str__(self):
        return 'Student object (name: %s, score: %d)' % (self.__name, self.__score)    

S = Student("Alexdu", 99)
print(S)

# cannot access private variable
# print(S.__name)

# but can access private variable with _Student__name
print(S._Student__name)

# can add new attribute to instance
S.age = 20
print(S.age)


