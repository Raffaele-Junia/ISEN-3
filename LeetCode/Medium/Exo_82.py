class ListNode(object):
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next


class Solution(object):
    def deleteDuplicates(self, head):
        dummy=ListNode(0,head)
        prev=dummy
        while head:
            if head.next and head.val==head.next.val:
                bot = head.val
                while head and bot == head.val:
                    head=head.next
                prev.next=head
            else:
                prev=head
                head=head.next
        return dummy.next



        