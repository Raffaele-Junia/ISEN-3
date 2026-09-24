class Solution(object):
    def singleNumber(self, nums):
        dic={}
        good=[]
        for char in nums:
            dic[char]=dic.get(char,0)+1
        for cle, valeur in dic.items():
            if valeur==1:
                good.append(cle)
        return good

"Parmi une liste de nombres, cette fonction retourne tous les nombres qui n'apparaissent qu'une seule fois dans la liste."