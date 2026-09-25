class Solution(object):

    def numWaterBottles(self, numBottles, numExchange):
        num = 0
        dic = {"bot": numBottles, "botv": 0}

        while dic["bot"] > 0:
            num += dic["bot"]
            dic["botv"] += dic["bot"]
            dic["bot"] = 0

            dic["bot"] = dic["botv"] // numExchange
            dic["botv"] = dic["botv"] % numExchange

        return num
print(Solution().numWaterBottles(14,6))
"Nombre de bouteilles d'eau bu, avec un échange de bouteilles vides contre de nouvelles bouteilles d'eau."