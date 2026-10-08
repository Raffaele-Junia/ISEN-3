class Solution(object):
    def searchMatrix(self, matrix, target):
        rows = len(matrix)
        columns = len(matrix[0])

        row = 0
        column = columns - 1
        while row < rows and column>=0:
            current = matrix[row][column]

            if current == target:
                return True
            elif current > target:
                column-=1
            else:
                row+=1
        return False