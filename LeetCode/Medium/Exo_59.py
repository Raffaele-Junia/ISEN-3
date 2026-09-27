class Solution(object):
    def generateMatrix(self, n):
        matrix = [[0 for _ in range(n)] for _ in range(n)]
        left=0
        top=0
        bottom=n-1
        right=n-1
        u=1
        while left<=right and top<=bottom:
            for i in range(left,right+1):
                matrix[top][i]=u
                u+=1
            top+=1
            for k in range(top,bottom+1):
                matrix[k][right]=u
                u+=1
            right-=1
            if top<=bottom:
                for o in range(right,left-1,-1):
                    matrix[bottom][o]=u
                    u+=1
                bottom-=1
            if left<=right:
                for j in range(bottom,top-1,-1):
                    matrix[j][left]=u
                    u+=1
                left+=1
        return matrix
        