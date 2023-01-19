import shutil
import os

NB_FILES = 2
NB_TES = 100000
DIR = os.path.join(os.getcwd(), "generated_tree")

TE_PER_FILE = int(NB_TES / NB_FILES)
TREE_MATRIX = []
TREE_IDX = 0


if __name__ == '__main__':
    print(f"Building {NB_FILES} files with {TE_PER_FILE} files per file")
    for d in range(1, NB_FILES+1):

        subdirectory = os.path.join(DIR, "d{}".format(d%NB_FILES))
        TREE_IDX += 1

        if not os.path.isdir(subdirectory):
            os.makedirs(subdirectory)

        print(subdirectory)
        with open(os.path.join(subdirectory, "pcvs.yml"), 'w') as fh:
            for te in range(0, TE_PER_FILE):
                fh.write(f"""te_{te}: {{"run": {{"program": "echo 'this is test te_{te}'"}}}}\n""")


