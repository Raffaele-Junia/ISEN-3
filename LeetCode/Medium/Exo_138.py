class Solution(object):
    def canCompleteCircuit(self, gas, cost):
        current_gas=0
        start=0
        total_gas=0
        for i in range(len(gas)):
            fuel_gain=gas[i]-cost[i]
            total_gas+=fuel_gain
            current_gas+=fuel_gain
            if current_gas<0:
                current_gas=0
                start=i+1
        return -1 if total_gas<0 else start
            
"Renvoie l'indice de la station de départ à partir de laquelle on peut faire le tour complet du circuit, ou -1 si ce n'est pas possible."