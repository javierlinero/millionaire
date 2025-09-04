import random

# Doubly circular linked list implementation for the monopoly board, this allows for traversing back when going to jail & forth when moving normally
# Implementations needed:
# - Add class for player w/ position pointer, money, properties owned, in_jail status
# - Add a method to move a player based on dice roll
# - Add a trading mechanism between players
# - Add property management (buying, selling, renting) <- limit the # of properties as well
# - Add a method to declare bankruptcy
# - Add winning condition (easy pz)
# - Add chance/community chest cards (draw from a deck, implement the effects)
# - Add a method to display the current state of the board and players
# - Add specific rental values and property details
# - Add a method to handle turns and game flow
# - Add a method to handle special cards (when you owe money to another player(s))

class Player:
    def __init__(self, name):
        self.name = name
        self.position = None  
        self.money = 372_000
        self.properties = []
        self.in_jail = False

class Position:
    def __init__(self, data=None):
        self.data = data
        self.prev = None
        self.next = None


class MonopolyBoard:
    def __init__(self):
        self.head = None

    def append(self, data):
        new_node = Position(data)
        if not self.head:
            self.head = new_node
            new_node.next = new_node
            new_node.prev = new_node
            return

        last = self.head.prev

        # insert new_node between last and head
        last.next = new_node
        new_node.prev = last
        new_node.next = self.head
        self.head.prev = new_node

    def display(self):
        if not self.head:
            print("List is empty")
            return

        current = self.head
        while True:
            print(current.data['Name'], end=" -> ")
            current = current.next
            if current == self.head:
                break
        print(current.data['Name'])

if __name__ == "__main__":
    loc = [{'Name' : 'Go'}, 
           {'Name' : 'Motor Drive', 'Price': 5_000, 'Color': 'Brown'},
           {'Name' : 'Millionaire Lifestyle'},
           {'Name' : 'Gadget Wharf', 'Price': 5_000, 'Color': 'Brown'},
           {'Name' : 'Surfer\'s Cove', 'Price': 15_000, 'Color': 'Light Blue'},
           {'Name' : 'Chance'},
           {'Name' : 'Aqua Park Resort', 'Price': 15_000, 'Color': 'Light Blue'},
           {'Name' : 'Lakeside Marina', 'Price': 20_000, 'Color': 'Light Blue'},
           {'Name' : 'Jail'},
           {'Name' : 'Castle View', 'Price': 35_000, 'Color': 'Pink'},
           {'Name' : 'Dream Avenue', 'Price': 35_000, 'Color': 'Pink'},
           {'Name' : 'Palace Gardens', 'Price': 40_000, 'Color': 'Pink'},
           {'Name' : 'Adventure Park', 'Price': 55_000, 'Color': 'Orange'},
           {'Name' : 'Millionaire Lifestyle'},
           {'Name' : 'Themepark City', 'Price': 55_000, 'Color': 'Orange'},
           {'Name' : 'Movie District', 'Price': 60_000, 'Color': 'Orange'},
           {'Name' : 'Free Parking'},
           {'Name' : 'Style Square', 'Price': 80_000, 'Color': 'Red'},
           {'Name' : 'Chance'},
           {'Name' : 'Party Plaza', 'Price': 80_000, 'Color': 'Red'},
           {'Name' : 'Showtime Boulevard', 'Price': 90_000, 'Color': 'Red'},
           {'Name' : 'Sunshine Bay', 'Price': 115_000, 'Color': 'Yellow'},
           {'Name' : 'Bling Beach', 'Price': 115_000, 'Color': 'Yellow'},
           {'Name' : 'Yacht Harbor', 'Price': 120_000, 'Color': 'Yellow'},
           {'Name' : 'Go to Jail'},
           {'Name' : 'Treetop Retreat', 'Price': 145_000, 'Color': 'Green'},
           {'Name' : 'Ski Mountain', 'Price': 145_000, 'Color': 'Green'},
           {'Name' : 'Millionaire Lifestyle'},
           {'Name' : 'Diamond Hills', 'Price': 150_000, 'Color': 'Green'},
           {'Name' : 'Chance'},
           {'Name' : 'Fortune Valley', 'Price': 170_000, 'Color': 'Dark Blue'},
           {'Name' : 'Paradise Island', 'Price': 200_000, 'Color': 'Dark Blue'},]


    ll = MonopolyBoard()

    for item in loc:
        ll.append(item)

    curr = ll.head

    for _ in range(3):
        x1 = random.randint(1, 6)
        x2 = random.randint(1, 6)

        steps = x1 + x2
        print(f"Dice rolled: {x1} + {x2} = {steps}")
        for _ in range(steps):
            curr = curr.next
            print(f"Moving to: {curr.data['Name']}")

        # print(f"Moved to: {curr.data['Name']}")
        if curr.data['Name'] == 'Go to Jail':
            while True:
                curr = curr.prev
                print(f"Moving back: {curr.data['Name']}")
                if curr.data['Name'] == 'Jail':
                    # print("Sent to Jail!")
                    break

    # ll.display()