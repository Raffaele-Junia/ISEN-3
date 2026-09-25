class Solution(object):
    def maxArea(self, height):
        left=0
        right=len(height)-1
        max_h=0
        while left<right:
            h=min(height[left],height[right])
            max_h=max(max_h,h*(right-left))
            if height[left]<height[right]:
                left+=1
            else:
                right-=1
        return max_h

print(Solution().maxArea([1,8,6,2,5,4,8,3,7]))
"Renvoie l'aire maximum d'eau que l'on peut contenir entre les lignes représentées par la liste 'height'."