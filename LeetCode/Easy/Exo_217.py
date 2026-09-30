class Solution(object):
    def containsDuplicate(self, nums):
        dic1={}
        for num in nums:
            if num in dic1:
                return True
            else:
                dic1[num]=1
        return False

