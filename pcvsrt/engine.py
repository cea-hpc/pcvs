import itertools


class Engine:
    def __init__(self):
        pass

    def generate_combinations(self, *lists):
        for combination in list(itertools.product(*lists)):
            yield combination


if __name__ == '__main__':
    test = Engine()
    for i in test.generate_combinations(
            [1, 2, 3, 4],
            ['a', 'b', 'd'],
            [0.4, 2, 'test']):
        print(i)
