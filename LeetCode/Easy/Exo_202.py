class Solution(object):
    def isHappy(self, n):
        visit=set()
        def get_next(n):
            output=0

            while n:
                digit = n%10
                output+=digit**2
                n=n//10
            return output
        while n not in visit:
            visit.add(n)
            n=get_next(n)
            if n==1:
                return True
        return False
