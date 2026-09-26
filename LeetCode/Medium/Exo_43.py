class Solution(object):
    def multiply(self, num1, num2):
        n,m=len(num1),len(num2)
        result=[0]*(n+m)
        for i in range(n-1,-1,-1):
            for j in range(m-1,-1,-1):
                mul=(ord(num1[i])-ord('0'))*(ord(num2[j])-ord('0'))
                num_=mul+result[i+j+1]
                result[i+j+1]=num_%10
                result[i+j]+=num_//10
        produit="".join(map(str,result)).lstrip('0')
        return produit if produit else '0'
