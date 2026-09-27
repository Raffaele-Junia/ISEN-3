from collections import defaultdict

class Solution(object):
    def isValidSudoku(self, board):
        rows= defaultdict(set)
        cols= defaultdict(set)
        boxes= defaultdict(set)
        for i in range(9):
            for j in range(9):
                if board[i][j]==".":
                    continue
                if board[i][j] in rows[i] or board[i][j] in cols[j] or board[i][j] in boxes[(i//3,j//3)]:
                    return False
                rows[i].add(board[i][j])
                cols[j].add(board[i][j])
                boxes[(i//3),(j//3)].add(board[i][j])
        return True

