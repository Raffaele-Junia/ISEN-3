class Solution(object):
    def intersection(self, nums1, nums2):
        return (list(set(nums1) & set(nums2)))

"set est un ensemble au sens mathématique, c'est-à-dire qu'il ne contient pas de doublons. L'opérateur & permet de trouver l'intersection entre deux ensembles, c'est-à-dire les éléments communs aux deux ensembles. Ensuite, on convertit le résultat en liste pour obtenir le format souhaité."