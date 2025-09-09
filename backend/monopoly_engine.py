import random
from collections import deque
from functools import partial

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
        self.mover_type = None 
        self.mover_level = 0
        self.position = None  
        self.money = 372_000
        self.properties = []
        self.in_jail = False
        self.jail_free_card = False
        self.must_sell = False

    def __str__(self):
        return f"Player {self.name}, Money: {self.money}, Position: {self.position.data['Name'] if self.position else 'None'}"


class Position:
    def __init__(self, data=None):
        self.data = data
        self.prev = None
        self.next = None
        self.owner = None
        self.houses = 0 # hotel = 5 houses
        self.color = data.get('Color') if data and 'Color' in data else None

class Card:
    def __init__(self, description, effect, params):
        self.desc = description
        self.effect = effect # action is a callable that takes a player and game state
        self.effect_params = params or {}
    
    def apply(self, game, player):
        return self.effect(game, player, **self.effect_params)

def _earn_money(game, player, amount: int):
    player.money += amount
    return f"{player.name} earns ${amount}"

def _pay_player(game, player, amount: int, p2: Player):
    if player.money < amount:
        player.must_sell = True
        return f"{player.name} cannot pay ${amount} to {p2.name} (insufficient funds)"
    player.money -= amount
    p2.money += amount
    return f"{player.name} pays ${amount} to {p2.name}"

def _pay_all_players(game, player, amount: int):
    total_paid = 0
    messages = []
    
    for other_player in game.players:
        if other_player != player:
            if player.money < amount:
                player.must_sell = True
                messages.append(f"{player.name} cannot pay ${amount} to {other_player.name} (insufficient funds)")
                break
            player.money -= amount
            other_player.money += amount
            total_paid += amount
            messages.append(f"{player.name} pays ${amount} to {other_player.name}")
    
    return "; ".join(messages)

# collect from all players based on their levels amount: -> list (idx on mover level)
def _collect_from_all_players(game, player, amount: int):
    total_collected = 0
    messages = []
    
    for other_player in game.players:
        if other_player != player:
            if other_player.money < amount:
                other_player.must_sell = True
                messages.append(f"{other_player.name} cannot pay ${amount} to {player.name} (insufficient funds)")
            else:
                other_player.money -= amount
                player.money += amount
                total_collected += amount
                messages.append(f"{other_player.name} pays ${amount} to {player.name}")
    
    return "; ".join(messages)

def _go_to_jail(game, player):
    player.position = game.board.jail
    player.in_jail = True
    return f"{player.name} goes to Jail!"

def _advance_num_spaces(game, player, num):
    cur = player.position
    for _ in range(num):
        cur = cur.next
    player.position = cur
    return f"{player.name} advances to {cur.data['Name']}"

def _get_out_of_jail_free(game, player):
    player.jail_free_card = True
    return f"{player.name} can get out of Jail for free!"

def _use_jail_free_card(game, player):
    if player.jail_free_card:
        if not player.in_jail:
            return f"{player.name} is not in Jail!"
        player.in_jail = False
        player.jail_free_card = False
        return f"{player.name} uses a Get Out of Jail Free card!"
    return f"{player.name} does not have a Get Out of Jail Free card!"
    
### FORTUNE CARDS ### -> implement effects later (counterclockwise movement)



def make_decks():
    chance_deck = []
    millionaire_deck = []

    random.shuffle(chance_deck)
    random.shuffle(millionaire_deck)

    return deque(chance_deck), deque(millionaire_deck)

class MonopolyBoard:
    def __init__(self):
        self.head = None
        self.jail = None

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

        # store jail pointer
        if data["Name"] == "Jail":
            self.jail = new_node

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

    # def find_position_by_name(self, name):
    #     if not self.head:
    #         return None
    #     cur = self.head
    #     while True:
    #         if cur.data['Name'] == name:
    #             return cur
    #         cur = cur.next
    #         if cur is self.head:
    #             break
    #     return None

    def iter_nodes(self):
        if not self.head:
            return
        cur = self.head
        while True:
            yield cur
            cur = cur.next
            if cur is self.head:
                break

class MillionaireMonopoly:
    GO_BONUS = [150_000, 200_000, 250_000]
    JAIL_FINE = 50_000
    RENT_MAPPING = {
        'Brown': [5000, 25000],
        'Light Blue': [10000, 50000, 150000],
        'Pink': [20000, 100000, 300000],
        'Orange': [30000, 150000, 450000],
        'Red': [40000, 200000, 600000],
        'Yellow': [50000, 250000, 750000],
        'Green': [50_000, 125_000, 210_000, 320_000, 375_000, 485_000], #cost 55k
        'Dark Blue': [100000, 500000]
    }

    def __init__(self, board, players):
        # setup game state
        self.board = board
        self.players = [Player(name) for name in players]
        self.current_player_index = 0
        self.turns = 0
        # dice state
        self.d1 = 0
        self.d2 = 0
        self.double_rolls = 0
        self.game_over = False
        start_pointer = self.board.head # self.board.find_position_by_name('Go') or 
        for player in self.players:
            player.position = start_pointer

        self.chance_deck, self.millionaire_deck = make_decks()

    def roll_dice(self):
        self.d1 = random.randint(1, 6)
        self.d2 = random.randint(1, 6)
        return self.d1, self.d2
    
    def move_player(self, steps):
        player = self.players[self.current_player_index]
        for _ in range(steps):
            player.position = player.position.next
            if player.position.data['Name'] == 'Go':
                bonus = self.GO_BONUS[player.mover_level] # mover level determines bonus
                player.money += bonus
                print(f"{player.name} passed Go and collects ${bonus}!")
        self.current_player_index = (self.current_player_index + 1) % len(self.players)

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

    # curr = ll.head

    game = MillionaireMonopoly(ll, ['Alice', 'Bob', 'Charlie'])
    print("Initial Player States:")
    for p in game.players:
        print(f'player: {p.name}, position: {p.position.data["Name"]}, money: {p.money}')
    # Simulate a few turns
    for turn in range(10):
        d1, d2 = game.roll_dice()
        steps = d1 + d2
        print(f"Turn {turn + 1}: Dice rolled: {d1} + {d2} = {steps}")
        game.move_player(steps)
        print(f"{game.players[turn % len(game.players)].name} moved to: {game.players[turn % len(game.players)].position.data['Name']}")

    print("\nFinal Player States:")
    for p in game.players:
        print(f'player: {p.name}, position: {p.position.data["Name"]}, money: {p.money}')



    # for _ in range(4):
    #     x1 = random.randint(1, 6)
    #     x2 = random.randint(1, 6)

    #     steps = x1 + x2
    #     print(f"Dice rolled: {x1} + {x2} = {steps}")
    #     for _ in range(steps):
    #         curr = curr.next
    #         print(f"Moving to: {curr.data['Name']}")

    #     # print(f"Moved to: {curr.data['Name']}")
    #     if curr.data['Name'] == 'Go to Jail':
    #         while True:
    #             curr = curr.prev
    #             print(f"Moving back: {curr.data['Name']}")
    #             if curr.data['Name'] == 'Jail':
    #                 # print("Sent to Jail!")
    #                 break

    # ll.display()