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

    def clear(self):
        self.cards = []

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
        self.hand = Hand()
        self.split_hand = None

    def hit(self, card):
        self.hand.cards.append(card)

    def cards(self):
        return self.hand.cards

    def split(self, shoe):
        if len(self.hand.cards) == 2 and self.hand.cards[0].rank == self.hand.cards[1].rank:
            # Create a new split hand and move the second card from the original hand to the split hand
            self.split_hand = Hand()
            self.split_hand.cards.append(self.hand.cards.pop())
            # Deal a new card to each hand
            self.hand.cards.append(shoe.deal_card())
            self.split_hand.cards.append(shoe.deal_card())
            return True
        return False

    def clear(self):
        self.hand.clear()

    def __str__(self):
        return self.name


class Dealer(Player):
    def __init__(self, name="Dealer"):
        super().__init__(name)

    def should_hit(self):
        if self.hand.get_value() < 17:
            return True
        elif self.hand.get_value() == 17:
            for card in self.hand.cards:
                if card.rank == "A":
                    # if dealer has an ace as first card and the second card is less than 7, hit
                    if self.hand.cards.index(card) == 0 and self.hand.cards[1].value <= 6:
                        return True
                    # if dealer has an ace as second card and the first card is less than 7, hit
                    elif self.hand.cards.index(card) == 1 and self.hand.cards[0].value <= 6:
                        return True
                    else:
                        return False
            return False
        else:
            return False


class Blackjack:
    def __init__(self):
        self.shoe = Shoe()
        self.dealer = Dealer()
        self.players = []

    def add_player(self, player):
        self.players.append(player)

    def play_hand(self, player):
        player.clear()
        player.hit(self.shoe.deal_card())
        player.hit(self.shoe.deal_card())

        self.dealer.hand.clear()
        self.dealer.hand.cards.append(self.shoe.deal_card())
        self.dealer.hand.cards.append(self.shoe.deal_card())
        dealer_first_card = self.dealer.hand.cards[0]

        print(f"Dealer: {dealer_first_card}, [hidden]")

        hand = player.hand
        print(f"{hand}: {hand.get_value()}")
        if player.hand.get_value() == 21 and len(player.hand.cards) == 2 and any(
                card.rank in ('J', 'Q', 'K') for card in player.hand.cards):
            print("Natural blackjack!")
            return

        while True:
            print(f"{hand}: {hand.get_value()}")
            if len(hand.cards) == 2 and hand.cards[0].rank == hand.cards[1].rank:
                action = input("Hit, stand, or split? ")
                if action.lower() == "hit":
                    hand.cards.append(self.shoe.deal_card())
                    if hand.get_value() > 21:
                        print("Bust!")
                        break
                elif action.lower() == "stand":
                    break
                elif action.lower() == "split":
                    if player.split(self.shoe):
                        for split_hand in [player.hand, player.split_hand]:
                            print(f"Dealer: {dealer_first_card}, [hidden]")
                            while True:
                                print(f"{split_hand}: {split_hand.get_value()}")
                                action = input("Hit or stand? ")
                                if action.lower() == "hit":
                                    split_hand.cards.append(self.shoe.deal_card())
                                    if split_hand.get_value() > 21:
                                        print("Bust!")
                                        break
                                else:
                                    break
                        if player.hand.get_value() > 21 and player.split_hand.get_value() > 21:
                            print("Both hands bust! Dealer wins.")
                        elif player.hand.get_value() > 21:
                            print("First hand busts! Second hand wins.")
                        elif player.split_hand.get_value() > 21:
                            print("Second hand busts! First hand wins.")
                        elif player.hand.get_value() > player.split_hand.get_value():
                            print("First hand wins!")
                        elif player.hand.get_value() < player.split_hand.get_value():
                            print("Second hand wins!")
                        else:
                            print("It's a tie!")
                        break
                    else:
                        print("Cannot split!")
            else:
                action = input("Hit or stand? ")
                if action.lower() == "hit":
                    hand.cards.append(self.shoe.deal_card())
                    if hand.get_value() > 21:
                        print("Bust!")
                        break
                else:
                    break

        while self.dealer.should_hit():
            self.dealer.hit(self.shoe.deal_card())
        print(f"Dealer: {self.dealer.hand}: {self.dealer.hand.get_value()}")

        if player.hand.get_value() > 21:
            print("Player busts! Dealer wins.")
        elif self.dealer.hand.get_value() > 21:
            print("Dealer busts! Player wins.")
        elif player.hand.get_value() > self.dealer.hand.get_value():
            print("Player wins!")
        elif player.hand.get_value() < self.dealer.hand.get_value():
            print("Dealer wins!")
        else:
            print("It's a tie!")


k = Player(name='k')
game = Blackjack()
game.play_hand(k)