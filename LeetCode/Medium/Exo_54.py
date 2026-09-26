class Solution(object):
    def spiralOrder(self, matrix):
        left=0
        right=len(matrix[0])-1
        bottom=len(matrix)-1
        top=0
        result=[]
        while top<=bottom and left <=right:
            for i in range(left,right+1):
                result.append(matrix[top][i])
            top+=1
            for j in range(top,bottom+1):
                result.append(matrix[j][right])
            right-=1
            if top <= bottom:
                for k in range(right,left -1,-1):
                    result.append(matrix[bottom][k])
                bottom-=1
            if left<= right:
                for h in range(bottom,top-1,-1):
                    result.append(matrix[h][left])
                left+=1
        return result    

"parcourir en spirale une matrice"