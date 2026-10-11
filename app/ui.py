"""GARRY V7 dashboard UI: public market data only; live orders disabled."""
from math import cos, sin, pi
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from app.state import APPROVED_SYMBOLS, AppState
from data.market_feed import DeltaMarketFeed

BG = (0.012, 0.027, 0.060, 1)
CARD = (0.027, 0.060, 0.105, 1)
CARD2 = (0.045, 0.090, 0.145, 1)
WHITE = (0.91, 0.96, 1.00, 1)
MUTED = (0.56, 0.68, 0.79, 1)
BLUE = (0.10, 0.48, 0.90, 1)
BLUE_LIGHT = (0.30, 0.68, 1.00, 1)
TEAL = (0.08, 0.83, 0.74, 1)
GREEN = (0.18, 0.84, 0.61, 1)
RED = (1.00, 0.35, 0.38, 1)
ORANGE = (1.00, 0.68, 0.25, 1)


class Card(BoxLayout):
    def __init__(self, scale=1.0, **kwargs):
        self.scale = scale
        kwargs.setdefault("padding", dp(14) * scale)
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*CARD)
            self.bg = RoundedRectangle(pos=self.pos, size=self.size,
                                       radius=[dp(16) * scale])
        self.bind(pos=self._update_bg, size=self._update_bg)

    def _update_bg(self, *_):
        self.bg.pos, self.bg.size = self.pos, self.size


class NavIcon(Widget):
    def __init__(self, page_name, **kwargs):
        self.page_name, self.icon_color = page_name, MUTED
        super().__init__(**kwargs)
        self.bind(pos=self.redraw, size=self.redraw)

    def set_color(self, color):
        self.icon_color = color
        self.redraw()

    def redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        x, y = self.center
        s = min(self.width, self.height) * .72
        x1, x2, y1, y2 = x-s*.38, x+s*.38, y-s*.32, y+s*.32
        with self.canvas:
            Color(*self.icon_color)
            if self.page_name == "HOME":
                Line(points=[x-s*.48,y,x,y+s*.43,x+s*.48,y,x1,y,x1,y1,x2,y1,x2,y],width=1.5)
            elif self.page_name == "MARKETS":
                Line(points=[x1,y1,x1,y2,x2,y2],width=1.4)
                Line(points=[x-s*.29,y-s*.12,x-s*.08,y+s*.06,x+s*.08,y-s*.02,x+s*.30,y+s*.24],width=1.8)
            elif self.page_name == "TRADES":
                for off, length in [(s*.24,s*.48),(0,s*.62),(-s*.24,s*.48)]:
                    Line(points=[x-length/2,y+off,x+length/2,y+off],width=1.7)
            elif self.page_name == "ANALYSIS":
                Ellipse(pos=(x-s*.34,y-s*.2),size=(s*.53,s*.53))
                Line(points=[x+s*.1,y-s*.13,x+s*.39,y-s*.42],width=2)
            else:
                r=s*.28
                Ellipse(pos=(x-r,y-r),size=(2*r,2*r))
                Ellipse(pos=(x-s*.09,y-s*.09),size=(s*.18,s*.18))
                for i in range(8):
                    a=2*pi*i/8
                    Line(points=[x+cos(a)*s*.32,y+sin(a)*s*.32,
                                 x+cos(a)*s*.43,y+sin(a)*s*.43],width=1.8)


class NavItem(BoxLayout):
    def __init__(self, page_name, callback, **kwargs):
        super().__init__(**kwargs)
        self.page_name, self.callback = page_name, callback

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and not getattr(touch,"is_mouse_scrolling",False) and getattr(touch,"button",None) is None:
            self.callback(self.page_name)
            return True
        return super().on_touch_down(touch)


class DashboardUI(BoxLayout):
    """Core UI does not instantiate or depend on a paper trading session."""
    def __init__(self, state: AppState, **kwargs):
        super().__init__(orientation="vertical", spacing=0, **kwargs)
        self.state = state
        self.current_page = "HOME"
        self._resizing = False
        self.scale = self._get_scale()
        self.market_snapshots = {}
        self.market_error = ""
        self._market_feed_started = False
        self._last_refresh = 0.0
        self.market_feed = None
        try:
            self.market_feed = DeltaMarketFeed()
            self.market_feed.add_callback(self._on_market_snapshot)
        except Exception as exc:
            self.market_error = f"{type(exc).__name__}: {exc}"
        with self.canvas.before:
            Color(*BG)
            self.background = RoundedRectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_background, size=self._update_background)
        self.page = BoxLayout(orientation="vertical", size_hint=(1,1))
        self.add_widget(self.page)
        self.navigation = self.build_navigation()
        self.add_widget(self.navigation)
        self.show_home()
        Window.bind(size=self._on_window_size)

    def start_market_feed(self, *_):
        if self._market_feed_started:
            return
        try:
            if self.market_feed is None:
                self.market_feed = DeltaMarketFeed()
                self.market_feed.add_callback(self._on_market_snapshot)
            self.market_feed.start()
            self._market_feed_started = True
            self.market_error = ""
        except Exception as exc:
            self.market_error = f"{type(exc).__name__}: {exc}"
            self._refresh_market_page()

    def stop_market_feed(self, *_):
        if not self._market_feed_started:
            return
        try:
            if self.market_feed is not None:
                self.market_feed.stop()
        except Exception as exc:
            self.market_error = f"{type(exc).__name__}: {exc}"
        self._market_feed_started = False

    # main.py in the current repository calls this at shutdown. Safe no-op shim.
    def stop_paper(self, *_):
        return None

    def _on_market_snapshot(self, snapshot):
        Clock.schedule_once(lambda dt, item=snapshot: self._apply_snapshot(item), 0)

    def _apply_snapshot(self, snapshot):
        symbol = getattr(snapshot, "symbol", None)
        if symbol not in APPROVED_SYMBOLS:
            return
        self.market_snapshots[symbol] = snapshot
        if symbol == self.state.symbol:
            price = getattr(snapshot, "last_price", None)
            if price is None:
                price = getattr(snapshot, "price", None)
            try:
                if price is not None and float(price) > 0:
                    self.state.price = float(price)
                self.state.connection_status = self._snapshot_status(snapshot)
            except (ValueError, TypeError, AttributeError):
                pass
        now = Clock.get_time()
        if now - self._last_refresh >= 1:
            self._last_refresh = now
            self._refresh_market_page()

    def _snapshot_status(self, snap):
        if snap is None:
            return "OFFLINE"
        try:
            stale = getattr(snap, "is_stale", True)
            stale = stale() if callable(stale) else stale
            status = str(getattr(snap, "status", "OFFLINE")).upper()
            if stale:
                return "STALE" if getattr(snap, "last_price", None) else "OFFLINE"
            if status in ("CONNECTED", "LIVE"):
                return "LIVE"
            return status
        except Exception:
            return "STALE"

    def _price(self, symbol):
        snap = self.market_snapshots.get(symbol)
        if snap is None or self._snapshot_status(snap) != "LIVE":
            return None
        value = getattr(snap, "last_price", None)
        if value is None:
            value = getattr(snap, "price", None)
        try:
            value = float(value)
            return value if value > 0 else None
        except (TypeError, ValueError, OverflowError):
            return None

    def _updated_time(self, symbol):
        snap = self.market_snapshots.get(symbol)
        return str(getattr(snap, "updated_utc", "") or "No successful update")

    def _refresh_market_page(self):
        if self.current_page == "HOME":
            self.show_home()
            self.refresh_navigation()
        elif self.current_page == "MARKETS":
            self.show_markets()
            self.refresh_navigation()

    def show_notice(self, title, message):
        content = BoxLayout(orientation="vertical",padding=dp(16),spacing=dp(12))
        msg = Label(text=str(message),color=WHITE,halign="center",valign="middle")
        msg.bind(size=lambda w,s:setattr(w,"text_size",s))
        content.add_widget(msg)
        close = Button(text="OK",size_hint_y=None,height=dp(44),background_normal="",background_color=BLUE,color=WHITE)
        content.add_widget(close)
        popup = Popup(title=title,content=content,size_hint=(.85,None),height=dp(230),auto_dismiss=False)
        close.bind(on_release=popup.dismiss)
        popup.open()

    def _get_scale(self):
        return max(.82,min(1.12,(Window.width or dp(390))/dp(390)))
    def d(self,v): return dp(v)*self.scale
    def f(self,v): return sp(v)*self.scale

    def _on_window_size(self,*_):
        if self._resizing: return
        new=self._get_scale()
        if abs(new-self.scale)<.02: return
        self._resizing=True
        try:
            self.scale=new
            self.navigation.height=self.d(68)
            self.navigation.padding=self.d(5)
            self.navigate(self.current_page)
        finally: self._resizing=False

    def _update_background(self,*_):
        self.background.pos,self.background.size=self.pos,self.size

    def label(self,text,size=14,bold=False,color=WHITE,align="left"):
        w=Label(text=str(text),font_size=self.f(size),bold=bold,color=color,
                halign=align,valign="middle",shorten=False)
        w.bind(size=lambda item,value:setattr(item,"text_size",(max(0,value[0]-self.d(4)),value[1])))
        return w

    def button(self,text,height=48,accent=False):
        return Button(text=text,size_hint_y=None,height=self.d(height),font_size=self.f(13),
                      bold=True,color=WHITE,background_normal="",background_down="",
                      background_color=BLUE if accent else CARD2,border=(0,0,0,0))

    def make_card(self,orientation="horizontal",height=70,padding=14):
        return Card(scale=self.scale,orientation=orientation,size_hint_y=None,
                    height=self.d(height),padding=self.d(padding),spacing=self.d(8))

    def clear_page(self):
        self.page.clear_widgets()

    def scroll_container(self):
        scroll=ScrollView(do_scroll_x=False,do_scroll_y=True,bar_width=self.d(3),scroll_type=["content","bars"])
        box=BoxLayout(orientation="vertical",size_hint=(1,None),
                      padding=(self.d(12),self.d(10),self.d(12),self.d(18)),spacing=self.d(10))
        box.bind(minimum_height=box.setter("height"))
        scroll.add_widget(box); self.page.add_widget(scroll)
        return box

    def header(self,title,subtitle=""):
        h=BoxLayout(orientation="vertical",size_hint_y=None,height=self.d(68 if subtitle else 48),spacing=self.d(2))
        h.add_widget(self.label(title,23,True,WHITE,"center"))
        if subtitle: h.add_widget(self.label(subtitle,10,True,TEAL,"center"))
        return h

    def build_navigation(self):
        nav=BoxLayout(orientation="horizontal",size_hint_y=None,height=self.d(68),padding=(self.d(5),self.d(5)),spacing=self.d(2))
        with nav.canvas.before:
            Color(*CARD); nav.nav_background=RoundedRectangle(pos=nav.pos,size=nav.size,radius=[self.d(15)])
        nav.bind(pos=lambda _,v:setattr(nav.nav_background,"pos",v),size=lambda _,v:setattr(nav.nav_background,"size",v))
        self.nav_buttons={}; self.nav_icons={}; self.nav_indicators={}
        for name in ("HOME","MARKETS","TRADES","ANALYSIS","SETTINGS"):
            item=NavItem(page_name=name,callback=self.navigate,orientation="vertical",spacing=self.d(1),padding=(self.d(2),self.d(4)))
            with item.canvas.before:
                color=Color(*(BLUE if name==self.current_page else CARD))
                shape=RoundedRectangle(pos=item.pos,size=item.size,radius=[self.d(10)])
            item.bind(pos=lambda _,v,s=shape:setattr(s,"pos",v),size=lambda _,v,s=shape:setattr(s,"size",v))
            icon=NavIcon(name,size_hint=(1,.62))
            label=Label(text=name,size_hint=(1,.38),font_size=self.f(8.5),bold=True,color=TEAL if name==self.current_page else MUTED,halign="center",valign="middle")
            item.add_widget(icon); item.add_widget(label); nav.add_widget(item)
            self.nav_buttons[name]=label; self.nav_icons[name]=icon; self.nav_indicators[name]=(item,color,shape)
        return nav

    def refresh_navigation(self):
        for name,label in self.nav_buttons.items():
            active=name==self.current_page
            label.color=TEAL if active else MUTED
            self.nav_icons[name].set_color(TEAL if active else MUTED)
            _,color,_=self.nav_indicators[name]
            color.rgba=(BLUE[0],BLUE[1],BLUE[2],.25) if active else CARD

    def navigate(self,page):
        pages={"HOME":self.show_home,"MARKETS":self.show_markets,"TRADES":self.show_trades,"ANALYSIS":self.show_analysis,"SETTINGS":self.show_settings}
        if page not in pages: page="HOME"
        self.current_page=page; pages[page](); self.refresh_navigation()

    def change_symbol(self,spinner,value):
        if value not in APPROVED_SYMBOLS:
            spinner.text=self.state.symbol; return
        self.state.symbol=value
        snap=self.market_snapshots.get(value); price=self._price(value)
        if price is not None: self.state.price=price
        self.state.connection_status=self._snapshot_status(snap)
        self.show_home(); self.refresh_navigation()

    def show_home(self):
        self.clear_page(); box=self.scroll_container()
        box.add_widget(self.header("GARRY V7","SMC / ICT • MARKET DASHBOARD"))
        snap=self.market_snapshots.get(self.state.symbol); price=self._price(self.state.symbol); status=self._snapshot_status(snap)
        card=self.make_card(height=78); left=BoxLayout(orientation="vertical")
        left.add_widget(self.label("PUBLIC MARKET DATA",10,True,MUTED))
        left.add_widget(self.label(status,17,True,GREEN if status=="LIVE" else ORANGE))
        card.add_widget(left); card.add_widget(self.label("LIVE ORDERS DISABLED",10,True,BLUE_LIGHT,"right")); box.add_widget(card)
        if self.market_error: box.add_widget(self.label("Feed initialization: "+self.market_error,10,False,RED))
        market=self.make_card(orientation="vertical",height=164)
        row=BoxLayout(size_hint_y=None,height=self.d(38),spacing=self.d(6))
        row.add_widget(self.label("SELECT MARKET",11,True,MUTED))
        selector=Spinner(text=self.state.symbol,values=APPROVED_SYMBOLS,size_hint_x=None,width=self.d(128),font_size=self.f(12),background_normal="",background_color=CARD2,color=WHITE)
        selector.bind(text=self.change_symbol); row.add_widget(selector); market.add_widget(row)
        market.add_widget(self.label(f"{price:,.2f}" if price is not None else "--",27,True,WHITE,"center"))
        market.add_widget(self.label("Delta Exchange India • public ticker" if price is not None else "Waiting for fresh public market data",10,False,TEAL if price is not None else MUTED,"center"))
        market.add_widget(self.label("Updated: "+self._updated_time(self.state.symbol),8,False,MUTED,"center")); box.add_widget(market)
        scan=self.make_card(orientation="vertical",height=118)
        scan.add_widget(self.label("SMC / ICT SETUP STATUS",11,True,MUTED))
        scan.add_widget(self.label("NO TRADE",22,True,TEAL,"center"))
        scan.add_widget(self.label("Automated structure confirmation is not currently verified.",10,False,MUTED,"center")); box.add_widget(scan)
        safety=self.make_card(orientation="vertical",height=88)
        safety.add_widget(self.label("SAFETY STATUS",12,True,BLUE_LIGHT))
        safety.add_widget(self.label("Order placement disabled • Public data only • No API secrets stored",10,False,MUTED,"center")); box.add_widget(safety)

    def show_markets(self):
        self.clear_page(); box=self.scroll_container()
        box.add_widget(self.header("MARKETS","DELTA EXCHANGE INDIA • PUBLIC DATA"))
        for symbol in APPROVED_SYMBOLS:
            snap=self.market_snapshots.get(symbol); price=self._price(symbol); status=self._snapshot_status(snap)
            card=self.make_card(height=72); left=BoxLayout(orientation="vertical")
            left.add_widget(self.label(symbol,14,True)); left.add_widget(self.label(status,9,False,GREEN if status=="LIVE" else ORANGE))
            right=BoxLayout(orientation="vertical")
            right.add_widget(self.label(f"{price:,.2f}" if price is not None else "--",14,True,GREEN if price is not None else ORANGE,"right"))
            right.add_widget(self.label(self._updated_time(symbol),8,False,MUTED,"right"))
            card.add_widget(left); card.add_widget(right); box.add_widget(card)
        box.add_widget(self.label("Public prices only. No exchange orders are sent.",10,False,MUTED,"center"))

    def show_trades(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("TRADES","ORDER SAFETY"))
        card=self.make_card(orientation="vertical",height=140)
        card.add_widget(self.label("ORDER PLACEMENT DISABLED",16,True,ORANGE,"center"))
        card.add_widget(self.label("This build does not submit live exchange orders. No paper trading session is started or managed by this dashboard.",11,False,MUTED,"center")); box.add_widget(card)
        for name,value in (("LIVE ORDERS","DISABLED"),("API CREDENTIALS","NOT REQUIRED FOR PUBLIC DATA"),("EXCHANGE ACCOUNT","NOT CONNECTED")):
            item=self.make_card(height=52); item.add_widget(self.label(name,10,True,MUTED)); item.add_widget(self.label(value,10,True,WHITE,"right")); box.add_widget(item)

    def show_analysis(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("ANALYSIS","SMC / ICT MARKET STRUCTURE"))
        for name,value in (("MARKET STRUCTURE","NOT CALCULATED"),("BOS / CHOCH","NOT CALCULATED"),("LIQUIDITY SWEEP","NOT CALCULATED"),("ORDER BLOCK","NOT CALCULATED"),("FAIR VALUE GAP","NOT CALCULATED"),("IDM / INDUCEMENT","NOT CALCULATED"),("SIGNAL","NO TRADE")):
            card=self.make_card(orientation="vertical",height=58); card.add_widget(self.label(name,10,True,MUTED)); card.add_widget(self.label(value,12,True,TEAL if value=="NO TRADE" else WHITE)); box.add_widget(card)
        box.add_widget(self.label("SMC/ICT values remain unverified until the strategy engine is integrated and tested against market candles.",10,False,ORANGE))

    def retry_market_feed(self,*_):
        self.stop_market_feed(); self.market_error=""; self.start_market_feed(); self.show_settings(); self.refresh_navigation()

    def show_settings(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("SETTINGS","PUBLIC DATA • SAFETY"))
        data=self.make_card(orientation="vertical",height=116)
        data.add_widget(self.label("DELTA PUBLIC MARKET DATA",13,True,BLUE_LIGHT))
        data.add_widget(self.label("Public ticker requests do not need API credentials. Private keys are not collected or stored by this dashboard.",10,False,MUTED))
        data.add_widget(self.label("Feed: "+("RUNNING" if self._market_feed_started else "STOPPED"),11,True,GREEN if self._market_feed_started else ORANGE)); box.add_widget(data)
        feed=self.make_card(orientation="vertical",height=104)
        feed.add_widget(self.label("MARKET DATA CONNECTION",13,True))
        feed.add_widget(self.label(self.market_error or "Prices update through the public REST feed.",10,False,MUTED))
        retry=self.button("RETRY PUBLIC FEED",42,True); retry.bind(on_release=self.retry_market_feed); feed.add_widget(retry); box.add_widget(feed)
        trading=self.make_card(orientation="vertical",height=110)
        trading.add_widget(self.label("TRADING SAFETY",13,True,BLUE_LIGHT))
        trading.add_widget(self.label("LIVE ORDER PLACEMENT: DISABLED\nBiometric unlock is not implemented in this UI file; no authentication is claimed.",10,False,ORANGE)); box.add_widget(trading)

    # Compatibility callback only; does not create or control a paper engine.
    def start_paper(self,*_):
        self.show_notice("DISABLED","Paper Trading is not managed by this dashboard.")

    def emergency_stop(self,*_):
        self.show_notice("LIVE ORDERS DISABLED","No live exchange orders are enabled.")

