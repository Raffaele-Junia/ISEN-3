class Solution:
    def generate(self, numRows):
        if numRows == 0:
            return []
        if numRows == 1:
            return [[1]]
        
        PrevRow = self.generate(numRows-1)
        curr_row = [1] * numRows

        for i in range(1,numRows-1):
            curr_row[i] = PrevRow[-1][i-1]+PrevRow[-1][i]
        PrevRow.append(curr_row)
        return PrevRow
    
"Triangle de pascal"