class Solution(object):
    def singleNumber(self, nums):
        dic={}
        for char in nums:
            dic[char]=dic.get(char,0)+1
        for char in nums:
            if dic[char]==1:
                return char
"Fonction pour donner un nombre qui n'apparait qu'une seule fois dans une liste de nombres"