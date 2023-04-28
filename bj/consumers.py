import json
import traceback

from channels.generic.websocket import AsyncWebsocketConsumer
from blackjack_django.asgi import Shoe, Player, Dealer


class BlackjackGameConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player = None
        self.dealer = Dealer()
        self.shoe = Shoe(num_decks=2)
        self.bet = None

    async def connect(self):
        await self.channel_layer.group_add("blackjack", self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_good',
            'message': 'you re now connected'
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("blackjack", self.channel_name)

    async def play_round(self, hand_index):
        if self.player.hands[hand_index].is_blackjack() and hand_index + 1 == len(self.player.hands):
            await self.send_game_state()
            await self.send_cards()
            await self.determine_winner()
            await self.end_game()
            await self.reset_game()
            return
        elif self.player.hands[hand_index].is_blackjack() and hand_index + 1 < len(self.player.hands):
            await self.send(json.dumps({"type": "hand_index", "hand_index": hand_index + 1}))
            await self.send_cards()

        elif self.player.hands[0].is_splitable():
            await self.send(json.dumps({
                "type": "splitable",
            }))
        await self.send_cards()
        await self.send_game_state()

    async def play_hand(self, hand_index):
        await self.send_message(f'hand in hit: {hand_index}')
        if hand_index >= len(self.player.hands):
            await self.send_error("Invalid hand index")
            return

        hand = self.player.hands[hand_index]
        if hand.is_busted():
            await self.send_error("This hand is already busted")
        else:
            await self.send_message(f'this is {hand_index} hand')
            self.player.hit(hand_index, self.shoe)
            await self.send_cards()
            if hand.is_busted() and hand_index + 1 != len(self.player.hands):
                await self.send_game_state()
                await self.send(json.dumps({"type": "hand_index", "hand_index": hand_index + 1}))
            elif hand.is_busted() and hand_index + 1 == len(self.player.hands):
                await self.send_message(f'busteddddddd {hand_index}')
                await self.determine_winner()
                await self.end_game()
                await self.reset_game()

    async def play_dealer_turn(self):
        while self.dealer.should_hit():
            self.dealer.hit(0, self.shoe)

        await self.send_game_state()
        await self.determine_winner()
        await self.end_game()
        await self.reset_game()

    async def double_down(self, hand_index):
        hand = self.player.hands[hand_index]
        if self.player.chips >= self.bet:
            self.player.chips -= self.bet
            self.bet *= 2
            self.player.hit(hand_index, self.shoe)
            await self.send_cards()
            await self.send_game_state()
            if hand.is_busted():
                await self.determine_winner()
                await self.end_game()
                await self.reset_game()
            else:
                await self.play_dealer_turn()
        else:
            await self.send_error("You don't have enough chips to double down")

    async def split_hand(self, hand_index):
        hand = self.player.hands[hand_index]
        if hand.is_splitable():
            new_hand = hand.split_hand(self.shoe)
            self.player.add_hand(new_hand)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            message = json.loads(text_data)
            action_type = message["type"]

            if action_type == "join":
                player_name = message["name"]
                self.player = Player(player_name)
                self.player.chips = message["chips"]
                await self.send(json.dumps({
                    "type": "join",
                    "name": player_name,
                    "chips": self.player.chips
                }))

            elif action_type == "deal":
                self.bet = message["bet"]
                hand_index = message.get("hand", 0)
                if self.player.bet(self.bet) is None:
                    await self.send_error("You don't have enough chips")
                else:
                    self.player.hands[0].initial_cards(self.shoe)
                    self.dealer.hands[0].initial_cards(self.shoe)
                    await self.send_message(str(self.dealer.get_hand()))
                    await self.play_round(hand_index=hand_index)

            elif action_type == "hit":
                hand_index = message.get("hand", 0)
                await self.play_hand(hand_index)

            elif action_type == "stand":
                hand_index = message.get("hand", 0)
                if hand_index >= len(self.player.hands):
                    await self.send_error("Invalid hand index")
                else:
                    if hand_index + 1 < len(self.player.hands):
                        await self.send(json.dumps({"type": "hand_index", "hand_index": hand_index + 1}))
                    else:
                        await self.play_dealer_turn()

            elif action_type == "split":
                hand_index = message.get("hand", 0)
                if hand_index >= len(self.player.hands):
                    await self.send_error("Invalid hand index")
                else:
                    await self.split_hand(hand_index)
                    await self.play_round(hand_index=hand_index)
                    await self.send_cards()

            elif action_type == "double":
                hand_index = message.get("hand", 0)
                if hand_index >= len(self.player.hands):
                    await self.send_error("Invalid hand index")
                else:
                    await self.double_down(hand_index)

            else:
                await self.send_error("Invalid action type")

        except Exception as e:
            error_message = str(e)
            traceback_info = traceback.format_exc()
            await self.send_error(error_message)
            await self.send_message(f"Error details:\n{traceback_info}")

    async def send_error(self, error_message):
        await self.send(json.dumps({
            "type": "error",
            "message": error_message
        }))

    async def send_game_state(self):
        player_hands = []
        for hand in self.player.hands:
            player_hands.append({
                "cards": [str(card) for card in hand.cards],
                "value": hand.get_value(),
                "busted": hand.is_busted(),
                "blackjack": hand.is_blackjack(),
            })

        dealer_hand = {
            "cards": [str(card) for card in self.dealer.hands[0].cards],
            "value": self.dealer.hands[0].get_value(),
            "busted": self.dealer.hands[0].is_busted(),
            "blackjack": self.dealer.hands[0].is_blackjack()
        }

        game_state = {
            "type": "game_state",
            "player_hands": player_hands,
            "dealer_hand": dealer_hand,
            "chips": self.player.chips
        }

        await self.send(json.dumps(game_state))

        if self.shoe.cards_remaining() < 30:
            self.shoe = Shoe(num_decks=2)

    async def determine_winner(self):
        dealer_hand = self.dealer.get_hand()
        dealer_value = dealer_hand.get_value()

        for hand in self.player.hands:
            player_value = hand.get_value()
            bet = self.bet

            if hand.is_blackjack() and not dealer_hand.is_blackjack():
                # Player wins with blackjack
                self.player.chips += bet * 2.5
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"{self.player.name} wins with {hand} ({player_value}) = Blackjack!"
                }))
            elif not hand.is_blackjack() and dealer_hand.is_blackjack():
                # Dealer wins with blackjack
                self.player.chips -= bet
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"Dealer has blackjack with {dealer_hand} ({dealer_value})"
                }))
            elif hand.is_blackjack() and dealer_hand.is_blackjack():
                # Tie with both having blackjack
                self.player.chips += bet
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"{self.player.name} pushes with {hand} ({player_value})"
                }))
            elif player_value > 21:
                # Player busts
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"{self.player.name} busts with {hand} ({player_value})"
                }))
            elif dealer_value > 21:
                # Dealer busts, player wins
                self.player.chips += bet * 2
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"{self.player.name} wins with {hand} ({player_value})"
                }))
            elif player_value == dealer_value:
                # Tie with equal values
                self.player.chips += bet
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"{self.player.name} ties with {hand} ({player_value})"
                }))
            elif player_value > dealer_value:
                # Player wins with higher value
                self.player.chips += bet * 2
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"{self.player.name} wins with {hand} ({player_value})"
                }))
            else:
                # Player loses
                await self.send(json.dumps({
                    "type": "winner",
                    "message": f"{self.player.name} loses with {hand} ({player_value})"
                }))

    async def send_cards(self):
        card_data = {
            "type": "cards",
            "player_cards": [],
            "dealer_card": str(self.dealer.getFirstCard())
        }
        for hand in self.player.hands:
            hand_cards = [str(card) for card in hand.cards]
            card_data["player_cards"].append(hand_cards)
        await self.send(json.dumps(card_data))

    async def reset_game(self):
        self.player = self.player
        self.dealer = Dealer()
        self.player.clear_hands()
        self.dealer.clear_hands()
        await self.send(json.dumps({"type": "reset"}))
        await self.send(json.dumps({"type": "hand_index", "hand_index": 0}))

    async def end_game(self):
        await self.send(json.dumps({
            "type": "end_game",
            "dealer_cards": [str(card) for card in self.dealer.hands[0].cards],
            "dealer_value": self.dealer.hands[0].get_value(),
            "dealer_busted": self.dealer.hands[0].is_busted(),
            "dealer_blackjack": self.dealer.hands[0].is_blackjack(),
            "player_chips": self.player.chips
        }))

    async def send_message(self, message):
        await self.send(json.dumps({
            "type": "message",
            "message": message
        }))

    async def send_all(self, message):
        await self.channel_layer.group_send("blackjack", {
            "type": "chat_message",
            "message": message
        })

    async def chat_message(self, event):
        message = event["message"]
        await self.send(json.dumps({
            "type": "message",
            "message": message
        }))

    async def add_to_group(self, group_name):
        await self.channel_layer.group_add(
            group_name,
            self.channel_name
        )

    async def remove_from_group(self, group_name):
        await self.channel_layer.group_discard(
            group_name,
            self.channel_name
        )
