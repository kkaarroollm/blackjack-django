import random

suits = ("Hearts", "Diamonds", "Clubs", "Spades")
ranks = ("2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A")


class Card:
    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank

    @property
    def value(self):
        if self.rank in ("J", "Q", "K"):
            return 10
        elif self.rank == "A":
            return 11
        else:
            return int(self.rank)

    def __str__(self):
        return f"{self.rank} of {self.suit}"

    def __repr__(self):
        return self.__str__()


class Shoe:
    def __init__(self, num_decks=2):
        self.cards = []
        for _ in range(num_decks):
            for suit in suits:
                for rank in ranks:
                    self.cards.append(Card(suit, rank))
        self.shuffle()

    def shuffle(self):
        random.shuffle(self.cards)

    def deal_card(self):
        return self.cards.pop(0)

    def cards_remaining(self):
        return len(self.cards)


class Hand:
    def __init__(self):
        self.cards = []

    def initial_cards(self, shoe):
        self.cards.append(shoe.deal_card())
        self.cards.append(shoe.deal_card())

    def add_card(self, card):
        self.cards.append(card)

    def is_busted(self):
        return self.get_value() > 21

    def is_blackjack(self):
        return len(self.cards) == 2 and self.get_value() == 21

    def is_splitable(self):
        return len(self.cards) == 2 and self.cards[0].rank == self.cards[1].rank

    def split_hand(self, shoe):
        if self.is_splitable():
            split_hand = Hand()
            split_hand.cards.append(self.cards.pop())
            self.cards.append(shoe.deal_card())
            split_hand.cards.append(shoe.deal_card())
            return split_hand
        else:
            return None

    def get_value(self):
        value = 0
        num_aces = 0
        for card in self.cards:
            value += card.value
            if card.rank == "A":
                num_aces += 1
        while value > 21 and num_aces > 0:
            value -= 10
            num_aces -= 1
        return value

    def __str__(self):
        return ", ".join(str(card) for card in self.cards)


class Player:
    def __init__(self, name):
        self.name = name
        self.hands = [Hand()]
        self.chips = 0

    def hit(self, hand_index, shoe):
        self.hands[hand_index].cards.append(shoe.deal_card())

    def get_hand(self, hand_index=0):
        return self.hands[hand_index]

    def bet(self, chips):
        if chips <= self.chips:
            self.chips -= chips
            return chips
        else:
            return None

    def clear_hands(self):
        self.hands = [Hand()]

    def add_hand(self, hand):
        self.hands.append(hand)

    def __str__(self):
        return self.name


class Dealer(Player):
    def __init__(self, name="Dealer"):
        super().__init__(name)

    def should_hit(self):
        if self.hands[0].get_value() < 17:
            return True
        elif self.hands[0].get_value() == 17:
            for card in self.hands[0].cards:
                if card.rank == "A":
                    if self.hands[0].cards.index(card) == 0 and self.hands[0].cards[1].value <= 6:
                        return True
                    elif self.hands[0].cards.index(card) == 1 and self.hands[0].cards[0].value <= 6:
                        return True
                    else:
                        return False
            return False
        else:
            return False


class BlackjackGame:
    def __init__(self, num_decks=2):
        self.shoe = Shoe(num_decks)
        self.dealer = Dealer()
        self.players = []

    def add_player(self, name):
        player = Player(name)
        player.chips = 500
        self.players.append(player)

    def deal_initial_cards(self):
        for player in self.players:
            player.get_hand().initial_cards(self.shoe)
        self.dealer.get_hand().initial_cards(self.shoe)

    def play_player_hands(self):
        for player in self.players:
            for hand in player.hands:
                while True:
                    print(f"{player.name}'s hand: {hand} ({hand.get_value()})")
                    if hand.is_splitable():
                        action = input("Do you want to hit, stand, split, or double down? ")
                    else:
                        action = input("Do you want to hit, stand, or double down? ")
                    if action.lower() == "hit":
                        hand.add_card(self.shoe.deal_card())
                        if hand.is_busted():
                            print(f"{player.name}'s hand: {hand} ({hand.get_value()})")
                            print("Busted!")
                            break
                    elif action.lower() == "stand":
                        break
                    elif action.lower() == "split":

                        new_hand = hand.split_hand(self.shoe)
                        player.add_hand(new_hand)
                        print(f"{player.name}'s original hand: {hand}")
                        print(f"{player.name}'s new hand: {new_hand}")
                        self.play_player_hands()
                        return
                    elif action.lower() == "double":
                        player.chips -= player.bet_amount
                        player.bet_amount *= 2
                        hand.add_card(self.shoe.deal_card())
                        print(f"{player.name}'s hand: {hand} ({hand.get_value()})")
                        break
        print()

    def play_dealer_hand(self):
        dealer_hand = self.dealer.get_hand()
        while self.dealer.should_hit():
            dealer_hand.cards.append(self.shoe.deal_card())
            if dealer_hand.is_busted():
                print(f"Dealer busts with {dealer_hand} ({dealer_hand.get_value()})")
                break
            elif dealer_hand.is_blackjack():
                print(f"Dealer has blackjack with {dealer_hand} ({dealer_hand.get_value()})")
                break
        if not dealer_hand.is_busted() and not dealer_hand.is_blackjack():
            print(f"Dealer stands with {dealer_hand} ({dealer_hand.get_value()})")

    def determine_winners(self):
        dealer_value = self.dealer.get_hand().get_value()
        dealer_hand = self.dealer.get_hand()
        print("Dealer's hand:", self.dealer.get_hand())
        print("Dealer's hand value:", dealer_value)
        for player in self.players:
            for hand in player.hands:
                player_value = hand.get_value()
                if hand.is_blackjack() and not dealer_hand.is_blackjack():
                    print(f"{player.name} wins with {hand} ({hand.get_value()}) = Blackjack!")
                    player.chips += player.bet_amount * 2.5
                elif not hand.is_blackjack() and dealer_hand.is_blackjack():
                    print(f"Dealer has blackjack with {dealer_hand} ({dealer_hand.get_value()})")
                    player.chips -= player.bet_amount
                elif hand.is_blackjack() and dealer_hand.is_blackjack():
                    print(f"{player.name} pushes with {hand} ({hand.get_value()})")
                    player.chips += player.bet_amount
                elif player_value > 21:
                    print(f"{player.name} busts with {hand} ({player_value})")
                elif dealer_value > 21:
                    print(f"{player.name} wins with {hand} ({player_value})")
                    player.chips += player.bet_amount * 2
                elif player_value == dealer_value:
                    print(f"{player.name} ties with {hand} ({player_value})")
                    player.chips += player.bet_amount
                elif player_value > dealer_value:
                    print(f"{player.name} wins with {hand} ({player_value})")
                    player.chips += player.bet_amount * 2
                else:
                    print(f"{player.name} loses with {hand} ({player_value})")
        print()

    def play_game(self):
        print("Welcome to Blackjack!")
        while True:
            num_players = int(input("How many players? "))
            if num_players <= 0:
                print("Invalid number of players. Please enter a positive integer.")
                continue
            for i in range(num_players):
                name = input(f"Enter player {i + 1}'s name: ")
                self.add_player(name)
            while True:

                for player in self.players:
                    while True:
                        bet_amount = int(input(f"{player.name}, how many chips do you want to bet? "))
                        if bet_amount > player.chips:
                            print(f"You don't have enough chips. You have {player.chips} chips left.")
                        else:
                            player.bet_amount = bet_amount
                            player.chips -= bet_amount
                            print(player.chips)
                            break
                self.deal_initial_cards()
                dealer_hand = self.dealer.get_hand()
                print(f"Dealer's hand: {dealer_hand.cards[0]}, [hidden card]")
                self.play_player_hands()
                if all(player.get_hand().is_busted() for player in self.players):
                    self.play_dealer_hand()
                    pass
                else:
                    print(f"Dealer's hand: {dealer_hand}")
                    self.play_dealer_hand()
                    self.determine_winners()
                for player in self.players:
                    print(player.bet_amount)
                    print(f"{player.name} has {player.chips} chips left.")
                    player.clear_hands()
                    self.dealer.clear_hands()
                    player.bet_amount = 0
                play_again = input("Do you want to play again? (y/n) ")
                if play_again.lower() == "n":
                    break
            break
        print("Thanks for playing!")



