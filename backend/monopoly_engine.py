import random
from collections import deque
from enum import Enum
from typing import List, Optional, Dict, Callable, Any

# Doubly circular linked list implementation for the monopoly board, this allows for traversing back when going to jail & forth when moving normally
# Implementations needed:
# - Add a trading mechanism between players (kinda done, just need to call transfer_property and send_money calls from UI)
# - Add a method to declare bankruptcy
# - Add winning condition (easy pz)
# - Add chance/community chest cards (draw from a deck, implement the effects)
# - Add a method to display the current state of the board and players
# - Add a method to handle special cards (when you owe money to another player(s))
# - Add a cache to players for full sets (to speed up rent calculation)

class GameState(Enum):
    PLAYING = "playing"
    WAITING_FOR_CHOICE = "waiting_for_choice"
    WAITING_FOR_PAYMENT = "waiting_for_payment"
    WAITING_FOR_PROPERTY_DECISION = "waiting_for_property_decision"
    GAME_OVER = "game_over"

class PendingAction:
    """Represents an action that requires user input"""
    def __init__(self, action_type: str, player: 'Player', description: str, 
                 choices: List[str] = None, callback: Callable = None, data: Dict = None):
        self.action_type = action_type
        self.player = player
        self.description = description
        self.choices = choices or []
        self.callback = callback
        self.data = data or {}

class Player:
    """ Represents a player in the game """
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
        self.must_pay_someone = False
        self.is_bankrupt = False

    def __str__(self):
        return f"Player {self.name}, Money: {self.money}, Position: {self.position.data['Name'] if self.position else 'None'}"


class Position:
    """ Represents a position on the board """
    def __init__(self, data=None):
        self.data = data
        self.prev = None
        self.next = None
        self.owner = None
        self.houses = 0 # hotel = 5 houses
        self.cost = data.get('Price') if data and 'Price' in data else 0
        self.color = data.get('Color') if data and 'Color' in data else None

class Card:
    """ Represents a Chance or Millionaire card """
    def __init__(self, description, effect, params):
        self.desc = description
        self.effect = effect # action is a callable that takes a player and game state
        self.effect_params = params or {}
    
    def apply(self, game, player):
        return self.effect(game, player, **self.effect_params)

def _pay_player_with_choice(game, player, amount: int):
    """This creates a pending state where player must choose who to pay"""
    other_players = [p for p in game.players if p != player and not p.is_bankrupt]
    
    if not other_players:
        return f"{player.name} has no one to pay!"
    
    def handle_choice(chosen_player_name):
        chosen_player = next((p for p in other_players if p.name == chosen_player_name), None)
        if chosen_player:
            if player.money < amount:
                player.must_sell = True
                return f"{player.name} cannot pay ${amount} to {chosen_player.name} (insufficient funds)"
            player.money -= amount
            chosen_player.money += amount
            return f"{player.name} pays ${amount} to {chosen_player.name}"
        return "Invalid choice"
    
    # Create pending action
    pending_action = PendingAction(
        action_type="choose_player_to_pay",
        player=player,
        description=f"Choose a player to pay ${amount} to:",
        choices=[p.name for p in other_players],
        callback=handle_choice,
        data={"amount": amount}
    )
    
    game.set_pending_action(pending_action)
    return "PENDING_CHOICE"

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

def _downgrade_mover(game, player):
    if player.mover_level > 0:
        player.mover_level -= 1
        return f"{player.name} downgrades their mover to level {player.mover_level}"
    return f"{player.name}'s mover is already at the lowest level"

def _upgrade_mover(game, player):
    if player.mover_level < 2:
        player.mover_level += 1
        return f"{player.name} upgrades their mover to level {player.mover_level}"
    else:
        player.money += 50_000
        return f"{player.name}'s mover is already at the highest level, receives $50,000 instead"

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
    """ Create and shuffle the Chance and Millionaire decks """
    chance_deck = []
    millionaire_deck = [Card("Go Straight to Jail. Do not pass Go. Do not collect your salary.", _go_to_jail, {}),
                        Card("Start your own business. To make $150,000, roll: doubles, 8-12, 5-12", )]

    random.shuffle(chance_deck)
    random.shuffle(millionaire_deck)

    return deque(chance_deck), deque(millionaire_deck)

class MonopolyBoard:
    """ Represents the Monopoly board as a doubly circular linked list """
    def __init__(self):
        self.head = None
        self.jail = None
        self.color_groups = {}

    def append(self, data):
        """ Append a new position to the board """
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

        # group by color for property sets safely -> to check if a player owns all properties of a color
        color = data.get("Color")
        if color:
            self.color_groups.setdefault(color, []).append(new_node)

    def display(self):
        """ Utility method to display the board positions """
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
    """ Main game class for Millionaire Monopoly """
    GO_BONUS = [150_000, 200_000, 250_000]
    JAIL_FINE = 50_000
    RENT_MAPPING = {
        'Brown': [7000, 15000, 30000, 50000, 60000, 80000], # 10k each
        'Light Blue': [15000, 30000, 50000, 80000, 95000, 125000], # cost 15k
        'Pink': [20000, 50000, 90000, 140000, 165000, 215000], # cost 25k each
        'Orange': [25000, 65000, 110000, 170000, 200000, 270000], # cost 30k
        'Red': [35000, 90000, 150000, 230000, 270000, 350000], # 35k
        'Yellow': [40000, 100000, 170000, 260000, 305000, 395000], # 45k
        'Green': [50000, 125000, 210000, 320000, 375000, 485000], #cost 55k
        'Dark Blue': [65000, 160000, 250000, 370000, 430000, 550000], # cost 60k
    }

    def __init__(self, board, players):
        # setup game state
        self.board = board
        self.players = [Player(name) for name in players]
        self.current_player_index = 0
        self.turns = 0

        self.state = GameState.PLAYING
        self.pending_action: Optional[PendingAction] = None
        self.action_queue = []

        # dice state
        self.d1 = 0
        self.d2 = 0
        self.double_rolls = 0
        self.game_over = False

        start_pointer = self.board.head # self.board.find_position_by_name('Go') or 
        for player in self.players:
            player.position = start_pointer

        self.chance_deck, self.millionaire_deck = make_decks()

    def set_pending_action(self, action: PendingAction):
        """Set a pending action and change game state"""
        self.pending_action = action
        self.state = GameState.WAITING_FOR_CHOICE

    def handle_pending_choice(self, choice: str) -> str:
        """Handle a user's choice for a pending action"""
        if not self.pending_action:
            return "No pending action"
        
        if choice not in self.pending_action.choices:
            return f"Invalid choice. Valid options: {', '.join(self.pending_action.choices)}"
        
        # Execute the callback
        result = self.pending_action.callback(choice)
        
        # Clear pending state
        self.pending_action = None
        self.state = GameState.PLAYING
        
        return result
    
    def get_game_state(self) -> Dict[str, Any]:
        """Get the current game state for the frontend"""
        state = {
            "game_state": self.state.value,
            "current_player": self.players[self.current_player_index].name,
            "turn": self.turns,
            "dice": [self.d1, self.d2],
            "players": [
                {
                    "name": p.name,
                    "money": p.money,
                    "position": p.position.data["Name"] if p.position else None,
                    "properties": [prop.data["Name"] for prop in p.properties],
                    "in_jail": p.in_jail,
                    "mover_level": p.mover_level,
                    "must_sell": p.must_sell
                }
                for p in self.players
            ]
        }
        
        if self.pending_action:
            state["pending_action"] = {
                "type": self.pending_action.action_type,
                "player": self.pending_action.player.name,
                "description": self.pending_action.description,
                "choices": self.pending_action.choices,
                "data": self.pending_action.data
            }
        
        return state
    
    def can_make_move(self) -> bool:
        """Check if the game can proceed with the next move"""
        return self.state == GameState.PLAYING and not self.game_over
    
    def handle_property_landing(self, player, position):
        """Handle when a player lands on a property - might create pending state"""
        if position.owner and position.owner != player:
            rent = self.calculate_rent(player, position)
            if rent > 0:
                if player.money < rent:
                    # Create pending state for selling assets
                    pending_action = PendingAction(
                        action_type="must_pay_rent",
                        player=player,
                        description=f"You owe ${rent} to {position.owner.name} for {position.data['Name']}. You must sell assets or declare bankruptcy.",
                        choices=["sell_assets", "declare_bankruptcy"],
                        data={"rent": rent, "owner": position.owner.name}
                    )
                    self.set_pending_action(pending_action)
                    return "PENDING_PAYMENT"
                else:
                    player.money -= rent
                    position.owner.money += rent
                    return f"{player.name} pays ${rent} rent to {position.owner.name}"
        elif not position.owner and position.cost > 0:
            # Create pending state for property purchase
            pending_action = PendingAction(
                action_type="property_purchase",
                player=player,
                description=f"Do you want to buy {position.data['Name']} for ${position.cost}?",
                choices=["buy", "pass"],
                data={"property": position, "cost": position.cost}
            )
            self.set_pending_action(pending_action)
            return "PENDING_PROPERTY_DECISION"
        
        return None

    def roll_dice(self):
        """Roll dice - only allowed if game can make a move"""
        if not self.can_make_move():
            return False
        
        self.d1 = random.randint(1, 6)
        self.d2 = random.randint(1, 6)
        return True
    
    def move_player(self, steps=None, upgrade_mover=False):
        """Move player and handle the resulting position"""
        if not self.can_make_move():
            return "Cannot move - game is in pending state"
        
        if steps is None:
            steps = self.d1 + self.d2
        
        player = self.players[self.current_player_index]
        
        # Move the player
        for _ in range(steps):
            player.position = player.position.next
            if player.position.data['Name'] == 'Go':
                bonus = self.GO_BONUS[player.mover_level]
                if upgrade_mover and player.mover_level < 2:
                    player.mover_level += 1
                    bonus -= 50_000 
                player.money += bonus
        
        position_name = player.position.data['Name']
        result = f"{player.name} moves to {position_name}"

        # Handle special positions
        if position_name == 'Go to Jail':
            _go_to_jail(self, player)
            result += " and goes to Jail!"
        elif position_name == 'Chance':
            if self.chance_deck:
                card = self.chance_deck.popleft()
                card_result = card.apply(self, player)
                self.chance_deck.append(card)
                if card_result != "PENDING_CHOICE":
                    result += f" | Chance Card: {card.desc} -> {card_result}"
                else:
                    result += f" | Chance Card: {card.desc} (awaiting choice)"
        elif position_name == 'Millionaire Lifestyle':
            if self.millionaire_deck:
                card = self.millionaire_deck.popleft()
                card_result = card.apply(self, player)
                self.millionaire_deck.append(card)
                if card_result != "PENDING_CHOICE":
                    result += f" | Millionaire Card: {card.desc} -> {card_result}"
                else:
                    result += f" | Millionaire Card: {card.desc} (awaiting choice)"
        else:
            # Handle property landing
            landing_result = self.handle_property_landing(player, player.position)
            if landing_result and not landing_result.startswith("PENDING"):
                result += f" | {landing_result}"

        # Only advance turn if no pending action
        if self.state == GameState.PLAYING:
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            self.turns += 1

        return result
    
    def buy_property(self, player, property):
        if property.owner is not None:
            return f"{property.data['Name']} is already owned by {property.owner.name}!"
        price = property.data.get('Price', 0)

        # this will be handled in the UI, but just in case
        if player.money < price:
            return f"{player.name} does not have enough money to buy {property.data['Name']}!"
        
        player.money -= price
        player.properties.append(property)
        property.owner = player
        return f"{player.name} buys {property.data['Name']} for ${price}."
    
    def transfer_property(self, from_player, to_player, property):
        if property not in from_player.properties:
            return f"{from_player.name} does not own {property.data['Name']}!"
        from_player.properties.remove(property)
        to_player.properties.append(property)
        property.owner = to_player
        return f"{from_player.name} transfers {property.data['Name']} to {to_player.name}."
    
    def send_money(self, from_player, to_player, amount):
        if from_player.money < amount:
            return f"{from_player.name} does not have enough money to pay ${amount} to {to_player.name}!"
        from_player.money -= amount
        to_player.money += amount
        return f"{from_player.name} pays ${amount} to {to_player.name}."
    
    def buy_house(self, player, property, cost_per_house, num=1):
        if property.owner != player:
            return f"{player.name} does not own {property.data['Name']}!"
        if property.houses >= 5:
            return f"{property.data['Name']} already has a hotel!"
        total_cost = num * cost_per_house
        if player.money < total_cost:
            return f"{player.name} does not have enough money to buy {num} house(s) on {property.data['Name']}!"
        
        property.houses += num
        player.money -= total_cost
        return f"{player.name} buys {num} house(s) on {property.data['Name']} for ${total_cost}."
    
    def owns_set(self, player, color) -> bool:
        props = self.board.color_groups.get(color)
        if not props:
            return False
        # all positions in that color group must be owned by `player`
        return all(getattr(p, "owner", None) == player for p in props)

    def has_houses(self, player, color) -> bool:
        props = self.board.color_groups.get(color)
        if not props:
            return False
        # any of the player's properties in that color has houses > 0
        return any(getattr(p, "owner", None) == player and getattr(p, "houses", 0) > 0
                   for p in props)

    def calculate_rent(self, player, position) -> int:
        owner = position.owner
        if owner is None or owner == player:
            return 0

        color = position.color or position.data.get("Color")
        mapping = MillionaireMonopoly.RENT_MAPPING.get(color)
        if mapping is None:
            return 0  # safe guard if code is wrong & no mapping exists

        idx = max(0, min(getattr(position, "houses", 0), len(mapping) - 1))
        rent = mapping[idx]

        # double rent if owner has the full set and NO houses anywhere in that set
        if self.owns_set(owner, color) and not self.has_houses(owner, color):
            rent *= 2

        return rent

    def move_player(self, steps, upgrade_mover=False) -> None:
        player = self.players[self.current_player_index]
        for _ in range(steps):
            player.position = player.position.next
            if player.position.data['Name'] == 'Go':
                bonus = self.GO_BONUS[player.mover_level] # mover level determines bonus
                if upgrade_mover and player.mover_level < 2:
                    player.mover_level += 1
                    print(f"{player.name} upgrades their mover to level {player.mover_level}!")
                    bonus -= 50_000 
                player.money += bonus
                print(f"{player.name} passed Go and collects ${bonus}!")
        
        position_name = player.position.data['Name']

        if position_name == 'Go to Jail':
            _go_to_jail(self, player)
            print(f"{player.name} goes directly to Jail!")
        elif position_name == 'Chance':
            if self.chance_deck:
                card = self.chance_deck.popleft()
                result = card.apply(self, player)
                print(f"Chance Card: {card.desc} -> {result}")
                self.chance_deck.append(card)
            else:
                print("Chance deck is empty!")
        elif position_name == 'Millionaire Lifestyle':
            if self.millionaire_deck:
                card = self.millionaire_deck.popleft()
                result = card.apply(self, player)
                print(f"Millionaire Card: {card.desc} -> {result}")
                self.millionaire_deck.append(card)
            else:
                print("Millionaire deck is empty!")
        else:
            # calculate the effect of landing on the new position
            cost = self.calculate_rent(player, player.position)
            if cost > 0:
                if player.money < cost:
                    player.must_sell = True
                    print(f"{player.name} cannot pay rent of ${cost} to {player.position.owner.name} (insufficient funds)")
                else:
                    player.money -= cost
                    player.position.owner.money += cost
                    print(f"{player.name} pays ${cost} rent to {player.position.owner.name} for landing on {player.position.data['Name']}")

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

    game = MillionaireMonopoly(ll, ['Alice', 'Bob', 'Charlie'])
    brown_props = game.board.color_groups.get('Brown', [])
    for p in brown_props:
        game.buy_property(game.players[0], p)  # Alice buys both brown properties

    pink_props = game.board.color_groups.get('Pink', [])
    for p in pink_props:
        game.buy_property(game.players[1], p)


    game.buy_house(game.players[0], brown_props[0], cost_per_house=10_000, num=3)  # Buy 1 house on Motor Drive
    print(game.calculate_rent(game.players[1], brown_props[0]))  # Should be 50k bc 3 houses
    print(game.calculate_rent(game.players[0], brown_props[0]))  # should be 0 
    print(game.calculate_rent(game.players[1], brown_props[1]))  # should be 7k bc no houses on that property

    print(game.owns_set(game.players[0], 'Brown'))  # True
    print(game.has_houses(game.players[0], 'Brown'))  # False


    print("Initial Player States:")
    for p in game.players:
        print(f'player: {p.name}, position: {p.position.data["Name"]}, money: {p.money}')
    
    
    # Simulate a few turns
    for turn in range(10):
        game.roll_dice()

        steps = game.d1 + game.d2
        print(f"\nTurn {turn + 1}: Dice rolled: {game.d1} + {game.d2} = {steps}")
        game.move_player(steps, upgrade_mover=True)
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