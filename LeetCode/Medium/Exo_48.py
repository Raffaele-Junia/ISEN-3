class Solution(object):
    def rotate(self, matrix):
        n=len(matrix)
        matrix2=[[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                matrix2[j][n-1-i]=matrix[i][j]
        return matrix2

"""class Solution(object):
    def rotate(self, matrix):
        n=len(matrix)
        for i in range(n):
            for j in range(i+1,n):
                matrix[i][j],matrix[j][i]=matrix[j][i],matrix[i][j]
        
        for i in range(n):
            matrix[i].reverse()

        return matrix
        
"""