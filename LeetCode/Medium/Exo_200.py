class Solution(object):
    def numIslands(self, grid):
        count=0
        cols, rows = len(grid[0]), len(grid)
        def dsf(row,col):
            if row < 0 or col>= cols or row>=rows or col<0:
                return
            if grid[row][col]!="1":
                return
            grid[row][col] = "0"
            dsf(row+1,col)
            dsf(row-1,col)
            dsf(row,col+1)
            dsf(row,col-1)
        for row in range(rows):
            for col in range(cols):
                if grid[row][col]=="1":
                    count+=1
                    dsf(row,col)
        return count