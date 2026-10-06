class Solution:
    def getSum(self, a: int, b: int) -> int:
        mask = 0xFFFFFFFF
        maxInt = 2**31

        while b!=0:
            s = (a ^ b) & mask
            c = (a & b) & mask
            a = s
            b = c << 1
        return a if a<maxInt else ~(a^mask)

"a+b sans utiliser l'operateur + ou -"