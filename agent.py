# !/usr/bin/env python3
# -*- coding: utf-8 -*-

from market import Market, Order, Trade

import abc
import pandas as pd
import textwrap

class BaseAgent(abc.ABC):

    def __init__(self, name):
        """
        Trading agent base class. Subclass BaseAgent to define how a concrete
        Agent should act given different market situations.

        :param name:
            str, agent name
        """

        self.name = name

        # containers for related class instances
        self.markets = Market.instances
        self.orders = Order.history
        self.trades = Trade.history

        # settings
        self.exposure_limit = 1e6 # ...
        self.latency = 0 # in milliseconds, used only in submit method
        self.cost_factor = 1e-3 # 10 bps

    # filter orders, trades ---

    def get_filtered_orders(self, market_id=None, side=None, status=None):
        """
        Filter Order.history based on market_id, side and status.

        :param market_id:
            str, market identifier, optional
        :param side:
            str, either 'buy' or 'sell', optional
        :param status:
            str, either 'ACTIVE', 'FILLED', 'CANCELLED' or 'REJECTED', optional
        :return orders:
            list, filtered Order instances
        """

        orders = self.orders

        # orders must have requested market_id
        if market_id:
            orders = filter(lambda order: order.market_id == market_id, orders)
        # orders must have requested side
        if side:
            orders = filter(lambda order: order.side == side, orders)
        # orders must have requested status
        if status:
            orders = filter(lambda order: order.status == status, orders)

        return list(orders)

    def get_filtered_trades(self, market_id=None, side=None):
        """
        Filter Trade.history based on market_id and side.

        :param market_id:
            str, market identifier, optional
        :param side:
            str, either 'buy' or 'sell', optional
        :return trades:
            list, filtered Trade instances
        """

        trades = self.trades

        # trades must have requested market_id
        if market_id:
            trades = filter(lambda trade: trade.market_id == market_id, trades)
        # trades must have requested side
        if side:
            trades = filter(lambda trade: trade.side == side, trades)

        return list(trades)

    # symbol, agent statistics ---

    @property
    def exposure(self):
        """
        Current net exposure that the agent has per market, based statically
        on the entry value of the remaining positions.

        Note that a positive and a negative value indicate a long and a short
        position, respectively.

        :return exposure:
            dict, {<market_id>: <exposure>, *}
        """

        result = dict()

        # ...
        for market_id, _ in self.markets.items():

            trd_buy = self.get_filtered_trades(market_id, side="buy")
            trd_sell = self.get_filtered_trades(market_id, side="sell")

            qty_buy = sum(t.quantity for t in trd_buy)
            qty_sell = sum(t.quantity for t in trd_sell)
            qty_unreal = qty_buy - qty_sell

            # buy side surplus
            if qty_unreal > 0:
                vwap_buy = sum(t.quantity * t.price for t in trd_buy) / qty_buy
                result_market = qty_unreal * vwap_buy
            # sell side surplus
            elif qty_unreal < 0:
                vwap_sell = sum(t.quantity * t.price for t in trd_sell) / qty_sell
                result_market = qty_unreal * vwap_sell
            # all quantity is realized
            else:
                result_market = 0

            result[market_id] = round(result_market, 3)

        return result

    @property
    def pnl_realized(self):
        """
        Current realized PnL that the agent has per market.

        :return pnl_realized:
            dict, {<market_id>: <pnl_realized>, *}
        """

        result = dict()

        # ...
        for market_id, _ in self.markets.items():

            trd_buy = self.get_filtered_trades(market_id, side="buy")
            trd_sell = self.get_filtered_trades(market_id, side="sell")

            qty_buy = sum(trade.quantity for trade in trd_buy)
            qty_sell = sum(trade.quantity for trade in trd_sell)
            qty_real = min(qty_buy, qty_sell)

            # qty_real is 0
            if not qty_real:
                result_market = 0
            # qty_real > 0
            else:
                vwap_buy = sum(t.quantity * t.price for t in trd_buy) / qty_buy
                vwap_sell = sum(t.quantity * t.price for t in trd_sell) / qty_sell
                result_market = qty_real * (vwap_sell - vwap_buy)

            result[market_id] = round(result_market, 3)

        return result

    @property
    def pnl_unrealized(self):
        """
        This method returns the unrealized PnL that the agent has per market.

        :return pnl_unrealized:
            dict, {<market_id>: <pnl_unrealized>, *}
        """

        result = dict()

        # ...
        for market_id, market in self.markets.items():

            trd_buy = self.get_filtered_trades(market_id, side="buy")
            trd_sell = self.get_filtered_trades(market_id, side="sell")

            qty_buy = sum(t.quantity for t in trd_buy)
            qty_sell = sum(t.quantity for t in trd_sell)
            qty_unreal = qty_buy - qty_sell

            # buy side surplus
            if qty_unreal > 0:
                vwap_buy = sum(t.quantity * t.price for t in trd_buy) / qty_buy
                result_market = abs(qty_unreal) * (market.best_bid - vwap_buy)
            # sell side surplus
            elif qty_unreal < 0:
                vwap_sell = sum(t.quantity * t.price for t in trd_sell) / qty_sell
                result_market = abs(qty_unreal) * (vwap_sell - market.best_ask)
            # all quantity is realized
            else:
                result_market = 0

            result[market_id] = round(result_market, 3)

        return result

    @property
    def exposure_total(self):
        """
        Current net exposure that the agent has across all markets, based on
        the net exposure that the agent has per market.

        Note that we use the absolute value for both long and short positions.

        :return exposure_total:
            float, total exposure across all markets
        """

        result = sum(abs(exposure) for _, exposure in self.exposure.items())
        result = round(result, 3)

        return result

    @property
    def pnl_realized_total(self):
        """
        Current realized pnl that the agent has across all markets, based on
        the realized pnl that the agent has per market.

        :return pnl_realized_total:
            float, total realized pnl across all markets
        """

        result = sum(pnl for _, pnl in self.pnl_realized.items())
        result = round(result, 3)

        return result

    @property
    def pnl_unrealized_total(self):
        """
        Current unrealized pnl that the agent has across all markets, based on
        the unrealized pnl that the agent has per market.

        :return pnl_unrealized_total:
            float, total unrealized pnl across all markets
        """

        result = sum(pnl for _, pnl in self.pnl_unrealized.items())
        result = round(result, 3)

        return result

    @property
    def exposure_left(self):
        """
        Current net exposure left before agent exceeds exposure_limit.

        :return exposure_left:
            float, remaining exposure
        """

        # TODO: include self.pnl_realized_total?
        result = self.exposure_limit - self.exposure_total
        result = round(result, 3)

        return result

    @property
    def transaction_costs(self):
        """
        Current trading costs based on trade history, accumulated throughout
        the entire backtest. Default

        :transaction_costs:
            float, accumulated transaction costs
        """

        result = self.cost_factor * sum(t.price * t.quantity for t in self.trades)
        result = round(result, 3)

        return result

    # event management ---

    @abc.abstractmethod
    def on_quote(self, market_id:str, book_state:pd.Series):
        """
        This method is called after a new quote.

        :param market_id:
            str, market identifier
        :param book_state:
            pd.Series, including timestamp, bid/ask price/quantity for ten levels
        """

        raise NotImplementedError("To be implemented in subclass.")

    @abc.abstractmethod
    def on_trade(self, market_id:str, trade_state:pd.Series):
        """
        This method is called after a new trade.

        :param market_id:
            str, market identifier
        :param trade_state:
            pd.Series, including timestamp, price, quantity
        """

        raise NotImplementedError("To be implemented in subclass.")

    @abc.abstractmethod
    def on_news(self, market_id:str, news_state:pd.Series):
        """
        This method is called after a news message.

        :param market_id:
            str, market identifier
        :param news_state:
            pd.Series, including timestamp, message
        """

        raise NotImplementedError("To be implemented in subclass.")

    @abc.abstractmethod
    def on_time(self, timestamp:pd.Timestamp, timestamp_next:pd.Timestamp):
        """
        This method is called with every iteration and provides the timestamps
        for both current and next iteration. The given interval may be used to
        submit orders before a specific point in time.

        :param timestamp:
            pd.Timestamp, timestamp recorded in this iteration
        :param timestamp_next:
            pd.Timestamp, timestamp recorded in next iteration
        """

        raise NotImplementedError("To be implemented in subclass.")

    # order management ---

    def _assert_exposure(self, market_id, side, quantity, limit):
        """
        Assert agent-related order parameters and provide information about
        an erroneous order submission. Note that program execution is supposed
        to continue.
        """

        # first, assert that market exists
        assert market_id in self.markets, \
            "market_id '{market_id}' is not available".format(
                market_id=market_id,
            )

        # limit order
        if limit:
            position_value = quantity * limit
        # market order, use reference price
        else:
            position_value = quantity * self.markets[market_id].mid_point

        # assert that exposure_left is not exceeded
        assert self.exposure_left >= position_value, \
            "{position_value} exceeds exposure_left {exposure_left}".format(
                position_value=position_value,
                exposure_left=self.exposure_left,
            )

    def submit_order(self, market_id, side, quantity, limit=None):
        """
        Submit market order, limit order if limit is specified. Note that all
        orders can be accessed through the Order.history class attribute, but,
        for convenience, this method also returns the order instance that can
        be used for cancellation.

        :param market_id:
            str, market identifier
        :param side:
            str, either 'buy' or 'sell'
        :param quantity:
            int, number of shares ordered
        :param limit:
            float, limit price to consider, optional
        :return order:
            Order, order instance
        """

        # assert agent exposure
        try:
            self._assert_exposure(market_id, side, quantity, limit)
        # block order if exposure_left is exceeded, return None
        except Exception as error:
            print("(SYSTEM) order was blocked upfront: {error}".format(
                error=error,
            ))
            return None

        # submit order
        order = Order(
            timestamp=Market.timestamp_global + pd.Timedelta(self.latency, "L"),
            market_id=market_id,
            side=side,
            quantity=quantity,
            limit=limit,
        )

        return order

    def cancel_order(self, order):
        """
        Cancel an active order.

        :param order:
            Order, order instance
        """

        # cancel order
        order.cancel()

    # string representation ---

    def __str__(self):
        """
        Provide string representation.
        """

        name = self.name
        timestamp, latency = Market.timestamp_global, self.latency

        exposure = self.exposure_total
        pnl_realized = self.pnl_realized_total
        pnl_unrealized = self.pnl_unrealized_total

        # string representation
        string = textwrap.dedent(f"""
        ---
        name:           {name}
        timestamp:      {timestamp} (+{latency} milliseconds)
        ---
        exposure:       {exposure}
        pnl_realized:   {pnl_realized}
        pnl_unrealized: {pnl_unrealized}
        """)

        # current mid price for all markets
        string = string + "\n---\nmarket mid price:\n"
        insert = "\n".join([f"{market_id}: {market.mid_point}"
            for market_id, market in self.markets.items()])
        string = string + insert

        # 5 most recent orders across all markets
        string = string + "\n---\n10 most recent orders:\n"
        insert = "\n".join([str(order) for order in self.orders[-10:]])
        string = string + insert

        # 5 most recent trades across all markets
        string = string + "\n---\n10 most recent trades:\n"
        insert = "\n".join([str(trade) for trade in self.trades[-10:]])
        string = string + insert

        return string