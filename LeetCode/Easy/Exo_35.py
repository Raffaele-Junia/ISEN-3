class Solution(object):
    def searchInsert(self, nums, target):
        x,y=0,len(nums)
        while x < y:
            z=x+(y-x)//2
            if nums[z]>target:
                y=z
            if nums[z]<target:
                x=z+1
            if nums[z]==target:
                return z
        return x

"binary search"