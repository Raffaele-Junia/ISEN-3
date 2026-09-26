class Solution(object):
    def isAnagram(self, s, t):
        if (len(s))!=(len(t)):
            return False
        dic={}
        dic2={}
        for i in range(len(s)):
            if s[i] not in dic:
                dic[s[i]]=0
            if t[i] not in dic2:
                dic2[t[i]]=0
            
            dic[s[i]]+=1
            dic2[t[i]]+=1
        return dic==dic2
        