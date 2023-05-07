import asyncio
import json
import traceback

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer

from blackjack_django.asgi import Shoe, Player, Dealer, User

channel_layer = get_channel_layer()


class BlackjackGameConsumer(AsyncWebsocketConsumer):
    room_shoes = {}
    timer_task = {}
    room_players = {}
    room_finished_hands = {}
    dealer_hand = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player = None
        self.dealer = Dealer()
        self.shoe = None
        self.bet = None

    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = 'blackjack_%s' % self.room_name

        if self.room_name not in self.room_shoes:
            self.room_shoes[self.room_name] = Shoe(num_decks=2)

        self.shoe = self.room_shoes[self.room_name]

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

        await self.send(text_data=json.dumps({
            'type': 'connection_good',
            'message': 'You are now connected to room %s' % self.room_name,
            'channel_name': self.channel_name,
            'cards_remaining': self.shoe.cards_remaining()
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            message = json.loads(text_data)
            action_type = message["type"]

            if action_type == "join":
                if self.player is not None:
                    return

                player_name = message["name"]
                player_chips = message["chips"]

                self.player = Player(player_name)
                self.player.chips = player_chips
                self.player.channel = self.channel_name

                room_name = self.room_name

                if room_name not in self.room_players:
                    self.room_players[room_name] = []

                self.room_players[room_name].append(self.player)

                print("Player joined:", player_name)
                print("Room players:", self.room_players)

                await self.send(json.dumps({
                    "type": "join",
                    "name": player_name,
                    "chips": player_chips
                }))

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'player_join',
                        'player_name': player_name
                    }
                )
            elif action_type == "deal":
                self.room_finished_hands[self.room_name] = set()

                if self.room_name not in self.timer_task or not self.timer_task[self.room_name]:
                    time_limit = 10
                    self.timer_task[self.room_name] = asyncio.create_task(asyncio.sleep(time_limit))

                await self.timer_task[self.room_name]
                if self.room_name not in self.dealer_hand or self.dealer_hand[self.room_name].hands[0].get_value() == 0:
                    self.dealer.hands[0].initial_cards(self.shoe)
                    self.dealer_hand[self.room_name] = self.dealer
                    print('-' * 20)
                    print(self.dealer.get_hand())
                    print('-' * 20)
                else:
                    self.dealer = self.dealer_hand[self.room_name]
                    print('hits here')
                    print('-' * 20)
                    print(self.dealer.get_hand())
                    print('-' * 20)
                await self.execute_deal(message)

            elif action_type == "hit" or action_type == "stand" or action_type == "split" or action_type == "double":
                if self.room_name not in self.timer_task or not self.timer_task[self.room_name]:
                    time_limit = 5
                    self.timer_task[self.room_name] = asyncio.create_task(asyncio.sleep(time_limit))
                await self.timer_task[self.room_name]

                if action_type == "hit":
                    hand_index = message.get("hand", 0)
                    await self.play_hand(hand_index)

                elif action_type == "stand":
                    hand_index = message.get("hand", 0)
                    if hand_index >= len(self.player.hands):
                        await self.send_error("Invalid hand index")
                    else:
                        self.room_finished_hands[self.room_name] = self.room_finished_hands.get(self.room_name, set())
                        self.room_finished_hands[self.room_name].add(self.player)
                        if len(self.room_finished_hands[self.room_name]) == sum(
                                len(player.hands) for player in self.room_players[self.room_name]):
                            await self.play_dealer_turn()
                        else:
                            await self.send(json.dumps({"type": "wait_for_players"}))

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

    async def player_join(self, event):
        player_name = event['player_name']
        await self.send(text_data=json.dumps({
            'type': 'player_join',
            'player_name': player_name
        }))

    async def execute_deal(self, message):
        self.bet = message["bet"]
        hand_index = message.get("hand", 0)
        if self.player.bet(self.bet) is None:
            await self.send_error("You don't have enough chips")
        else:
            self.player.hands[0].initial_cards(self.shoe)
            print(f'{self.player.name} has cards:{self.player.hands[0]}')
            await self.play_round(hand_index=hand_index)

    async def send_error(self, error_message):
        await self.send(json.dumps({
            "type": "error",
            "message": error_message
        }))

    async def play_round(self, hand_index):
        if self.player.hands[hand_index].is_blackjack() and hand_index + 1 == len(self.player.hands):
            await self.send_game_state()
            await self.send_cards()
            await self.end_game()
            # await self.reset_game()
            return
        elif self.player.hands[hand_index].is_blackjack() and hand_index + 1 < len(self.player.hands):
            await self.send(json.dumps({"type": "hand_index", "hand_index": hand_index + 1}))
            await self.send_cards()

        elif self.player.hands[hand_index].is_splitable():
            await self.send(json.dumps({
                "type": "splitable",
            }))
        await self.send_cards()
        await self.send_game_state()

    async def play_hand(self, hand_index):
        await self.send_message(f'Hand in hit: {hand_index}')
        if hand_index >= len(self.player.hands):
            await self.send_error("Invalid hand index")
            return

        hand = self.player.hands[hand_index]
        if hand.is_busted():
            await self.send_error("This hand is already busted")
            self.room_finished_hands[self.room_name] = self.room_finished_hands.get(self.room_name, set())
            self.room_finished_hands[self.room_name].add(hand)

            if len(self.room_finished_hands[self.room_name]) == sum(
                    len(player.hands) for player in self.room_players[self.room_name]):

                await self.determine_winner()
                await self.end_game()
                await self.reset_game()
            else:
                await self.send(json.dumps({"type": "wait_for_players"}))
        else:
            await self.send_message(f'This is hand {hand_index}')
            self.player.hit(hand_index, self.shoe)
            await self.send_cards()

            if hand_index + 1 != len(self.player.hands):
                await self.send_game_state()
                await self.send(json.dumps({"type": "hand_index", "hand_index": hand_index + 1}))

    async def play_dealer_turn(self):
        while self.dealer.should_hit():
            self.dealer.hit(0, self.shoe)

        await self.send_game_state()
        print('room')
        print(self.room_name)
        print('---')
        self.timer_task[self.room_name] = {}
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
                await self.end_game()
                # await self.reset_game()
            else:
                await self.play_dealer_turn()
        else:
            await self.send_error("You don't have enough chips to double down")

    async def split_hand(self, hand_index):
        hand = self.player.hands[hand_index]
        if hand.is_splitable():
            new_hand = hand.split_hand(self.shoe)
            self.player.add_hand(new_hand)
            print(f'new hand: {new_hand} and hand: {hand}')

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
        for player in self.room_players[self.room_name]:
            for hand in player.hands:
                player_value = hand.get_value()
                bet = self.bet

                if hand.is_blackjack() and not dealer_hand.is_blackjack():
                    # Player wins with blackjack
                    player.chips += bet * 2.5
                    message = f"{player.name} wins with {hand} ({player_value}) = Blackjack!"
                elif not hand.is_blackjack() and dealer_hand.is_blackjack():
                    # Dealer wins with blackjack
                    player.chips -= bet
                    message = f"Dealer has blackjack with {dealer_hand} ({dealer_value})"
                elif hand.is_blackjack() and dealer_hand.is_blackjack():
                    # Tie with both having blackjack
                    player.chips += bet
                    message = f"{player.name} pushes with {hand} ({player_value})"
                elif player_value > 21:
                    # Player busts
                    message = f"{player.name} busts with {hand} ({player_value})"
                elif dealer_value > 21:
                    # Dealer busts, player wins
                    player.chips += bet * 2
                    message = f"{player.name} wins with {hand} ({player_value})"
                elif player_value == dealer_value:
                    # Tie with equal values
                    player.chips += bet
                    message = f"{player.name} ties with {hand} ({player_value})"
                elif player_value > dealer_value:
                    # Player wins with higher value
                    player.chips += bet * 2
                    message = f"{player.name} wins with {hand} ({player_value})"
                else:
                    # Player loses
                    message = f"{player.name} loses with {hand} ({player_value})"

                print('-' * 20)
                print(player.channel)
                print('-' * 20)

                await self.send_message_to_channel(player.channel, message)

    async def send_message_to_channel(self, channel, message):
        winner = {
            'type': 'winner',
            'message': message
        }
        await self.channel_layer.send(
            channel,
            {
                "type": "winner",
                "message": json.dumps(winner)
            }
        )

    async def message(self, event):
        print(event['message'])
        await self.send(text_data=event['message'])

    async def winner(self, event):
        print(event['message'])
        await self.send(text_data=event['message'])

    async def send_cards(self):
        card_data = {
            "type": "cards",
            "player_name": self.player.name,
            "player_cards": [],
            "dealer_card": str(self.dealer.getFirstCard())
        }

        for hand in self.player.hands:
            hand_cards = [str(card) for card in hand.cards]
            card_data["player_cards"].append(hand_cards)

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'cards_message',
                'message': json.dumps(card_data)
            }
        )

    async def cards_message(self, event):
        await self.send(text_data=event['message'])

    async def reset_game(self):
        self.dealer_hand[self.room_name].clear_hands()
        for player in self.room_players[self.room_name]:
            self.player = player
            self.player.clear_hands()
            print(self.shoe)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'reset_message'
                }
            )
            await self.send(json.dumps({"type": "hand_index", "hand_index": 0}))

    async def reset_message(self, event):
        await self.send(json.dumps({"type": "reset"}))

    async def end_game(self):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'end_game_message',
                'dealer_cards': [str(card) for card in self.dealer.hands[0].cards],
                'dealer_value': self.dealer.hands[0].get_value(),
                'dealer_busted': self.dealer.hands[0].is_busted(),
                'dealer_blackjack': self.dealer.hands[0].is_blackjack(),
                'player_chips': self.player.chips
            }
        )

    async def end_game_message(self, event):
        await self.send(json.dumps({
            "type": "end_game",
            "dealer_cards": event['dealer_cards'],
            "dealer_value": event['dealer_value'],
            "dealer_busted": event['dealer_busted'],
            "dealer_blackjack": event['dealer_blackjack'],
            "player_chips": event['player_chips']
        }))

    async def send_message(self, message):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'message',
                'message': json.dumps(message)
            }
        )

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
