class Solution:
    def detectCycle(self, head):
        slow=fast=head
        while fast and fast.next:
            fast=fast.next.next
            slow=slow.next
            if fast==slow:
                break
        else: return None
        while head!=slow:
            head,slow=head.next,slow.next
        return head