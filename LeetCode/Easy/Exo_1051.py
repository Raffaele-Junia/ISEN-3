class Solution(object):
    def heightChecker(self, heights):
        return sum(h1!=h2 for h1,h2 in zip(heights,sorted(heights)))

print(Solution().heightChecker([1,1,4,2,1,3]))

"Nombre d'étudiants qui ne sont pas à la bonne place dans la file d'attente, en comparant la liste originale des hauteurs avec la liste triée des hauteurs."