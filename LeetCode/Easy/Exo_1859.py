class Solution(object):
    def sortSentence(self, s):
        words = sorted(s.split(" "), key=lambda x: int(x[-1]))
        return " ".join(word[:-1] for word in words)

print(Solution().sortSentence("is2 sentence4 This1 a3"))  # Output: "This is a sentence"
