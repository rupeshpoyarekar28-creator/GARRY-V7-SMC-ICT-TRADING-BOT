"""GARRY V7 dashboard UI. Public Delta market data only; live orders disabled."""
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
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from app.state import APPROVED_SYMBOLS, AppState
from app.trading_session import TradingSession
from data.market_feed import DeltaMarketFeed

BG=(.025,.023,.035,1); CARD=(.075,.070,.095,1); CARD2=(.105,.095,.135,1)
WHITE=(.96,.95,1,1); MUTED=(.58,.56,.65,1); PURPLE=(.48,.28,.95,1)
PURPLE_LIGHT=(.67,.52,1,1); GREEN=(.20,.85,.48,1); RED=(.95,.25,.32,1)
ORANGE=(1.,.62,.20,1)

class Card(BoxLayout):
    def __init__(self,scale=1.,**kw):
        self.scale=scale; kw.setdefault("padding",dp(14)*scale); super().__init__(**kw)
        with self.canvas.before:
            Color(*CARD); self.bg=RoundedRectangle(pos=self.pos,size=self.size,radius=[dp(16)*scale])
        self.bind(pos=self._upd,size=self._upd)
    def _upd(self,*_): self.bg.pos=self.pos; self.bg.size=self.size

class NavIcon(Widget):
    def __init__(self,page_name,**kw):
        self.page_name=page_name; self.icon_color=MUTED; super().__init__(**kw); self.bind(pos=self.redraw,size=self.redraw)
    def set_color(self,c): self.icon_color=c; self.redraw()
    def redraw(self,*_):
        self.canvas.clear(); w,h=self.width,self.height
        if w<=0 or h<=0:return
        x,y=self.center; s=min(w,h)*.72; x1,x2=x-s*.38,x+s*.38; y1,y2=y-s*.32,y+s*.32
        with self.canvas:
            Color(*self.icon_color)
            if self.page_name=="HOME": Line(points=[x-s*.48,y,x,y+s*.43,x+s*.48,y,x1,y,x1,y1,x2,y1,x2,y],width=1.5)
            elif self.page_name=="MARKETS": Line(points=[x1,y1,x1,y2,x2,y2],width=1.4); Line(points=[x-s*.29,y-s*.12,x-s*.08,y+s*.06,x+s*.08,y-s*.02,x+s*.30,y+s*.24],width=1.8)
            elif self.page_name=="TRADES":
                for off,l in [(s*.24,s*.48),(0,s*.62),(-s*.24,s*.48)]: Line(points=[x-l/2,y+off,x+l/2,y+off],width=1.7)
            elif self.page_name=="ANALYSIS": Ellipse(pos=(x-s*.34,y-s*.2),size=(s*.53,s*.53)); Line(points=[x+s*.1,y-s*.13,x+s*.39,y-s*.42],width=2)
            else:
                r=s*.28; Ellipse(pos=(x-r,y-r),size=(2*r,2*r)); Ellipse(pos=(x-s*.09,y-s*.09),size=(s*.18,s*.18))
                for i in range(8):
                    a=2*pi*i/8; Line(points=[x+cos(a)*s*.32,y+sin(a)*s*.32,x+cos(a)*s*.43,y+sin(a)*s*.43],width=1.8)

class DashboardUI(BoxLayout):
    def __init__(self,state:AppState,**kw):
        super().__init__(orientation="vertical",spacing=0,**kw)
        self.state=state; self.current_page="HOME"; self._resizing=False; self.scale=self._get_scale()
        self.paper_status="PAPER STOPPED"; self.paper_result={}; self.paper_error=""; self.mode="PAPER"
        self.market_snapshots={}; self.market_error=""; self._market_feed_started=False; self._last_refresh=0
        self.market_feed=DeltaMarketFeed(); self.market_feed.add_callback(self._on_market_snapshot)
        self.paper_session=TradingSession(on_update=self._on_paper_update,on_error=self._on_paper_error)
        with self.canvas.before: Color(*BG); self.background=RoundedRectangle(pos=self.pos,size=self.size)
        self.bind(pos=self._update_background,size=self._update_background)
        self.page=BoxLayout(orientation="vertical",size_hint=(1,1)); self.add_widget(self.page)
        self.navigation=self.build_navigation(); self.add_widget(self.navigation)
        self.show_home(); Window.bind(size=self._on_window_size)

    # Called by main.py only after successful login.
    def start_market_feed(self,*_):
        if self._market_feed_started:return
        try: self.market_feed.start(); self._market_feed_started=True; self.market_error=""
        except Exception as e: self.market_error=str(e); self._refresh_market_page()
    def stop_market_feed(self,*_):
        if not self._market_feed_started:return
        try:self.market_feed.stop()
        except Exception as e:self.market_error=str(e)
        self._market_feed_started=False
    def _on_market_snapshot(self,snapshot):
        Clock.schedule_once(lambda dt,s=snapshot:self._apply_snapshot(s),0)
    def _apply_snapshot(self,s):
        symbol=getattr(s,"symbol",None)
        if symbol not in APPROVED_SYMBOLS:return
        self.market_snapshots[symbol]=s
        if symbol==self.state.symbol:
            p=getattr(s,"last_price",None)
            if p is None:p=getattr(s,"price",None)
            try:
                if p is not None:self.state.price=float(p)
                self.state.connection_status=str(getattr(s,"status","CONNECTED"))
            except (ValueError,TypeError):pass
        now=Clock.get_time()
        if now-self._last_refresh>=1:
            self._last_refresh=now; self._refresh_market_page()
    def _price(self,symbol):
        s=self.market_snapshots.get(symbol)
        if s is None:return None
        stale=getattr(s,"is_stale",False)
        try:stale=stale() if callable(stale) else stale
        except Exception:stale=True
        if stale:return None
        p=getattr(s,"last_price",None)
        if p is None:p=getattr(s,"price",None)
        try:return float(p) if p is not None else None
        except (ValueError,TypeError):return None
    def _refresh_market_page(self):
        if self.current_page=="HOME":self.show_home(); self.refresh_navigation()
        elif self.current_page=="MARKETS":self.show_markets(); self.refresh_navigation()

    def _on_paper_update(self,result):
        self.paper_result=result or {}; self.paper_status=str(self.paper_result.get("status","PAPER UPDATE")); self.paper_error=""
        self.state.trading_enabled=self.paper_session.running
        if self.current_page=="HOME":self.show_home(); self.refresh_navigation()
        elif self.current_page=="TRADES":self.show_trades()
    def _on_paper_error(self,message):
        self.paper_error=str(message); self.paper_status="PAPER ERROR"
        if self.current_page=="HOME":self.show_home()
    def start_paper(self,*_):
        if self.mode!="PAPER":self.show_notice("MODE DISABLED","Only PAPER mode is available."); return
        try:
            self.paper_session.start_paper(self.state.symbol); self.paper_status="PAPER STARTING"; self.paper_error=""
            self.state.trading_enabled=True; self.show_home()
        except Exception as e:self.paper_error=str(e); self.paper_status="PAPER START FAILED"; self.show_notice("PAPER START ERROR",str(e))
    def stop_paper(self,*_):
        self.paper_session.stop(); self.state.trading_enabled=False; self.paper_status="PAPER STOPPED"; self.show_home()
    def select_mode(self,spinner,value):
        if value=="LIVE (DISABLED)":
            self.mode="PAPER"; spinner.text="PAPER"; self.show_notice("LIVE DISABLED","LIVE orders are not implemented. PAPER remains selected.")
        else:self.mode="PAPER"
    def stop_bot(self,*_):self.stop_paper()
    def save_api_notice(self,*_):self.show_notice("API SETUP","Private API credentials are not saved in this build.")
    def test_api_notice(self,*_):self.show_notice("API CONNECTION","Private API connection is not tested. Public market data only.")
    def emergency_stop(self,*_):
        self.stop_paper(); self.show_notice("PAPER STOPPED","PAPER session stopped. This is not a VPS/exchange kill switch.")

    def show_notice(self,title,message):
        content=BoxLayout(orientation="vertical",padding=dp(16),spacing=dp(12))
        msg=Label(text=message,color=WHITE,halign="center",valign="middle"); msg.bind(size=lambda i,v:setattr(i,"text_size",v)); content.add_widget(msg)
        close=Button(text="OK",size_hint_y=None,height=dp(44),background_normal="",background_color=PURPLE,color=WHITE); content.add_widget(close)
        popup=Popup(title=title,content=content,size_hint=(.85,None),height=dp(230),auto_dismiss=False); close.bind(on_release=popup.dismiss); popup.open()
    def _get_scale(self):return max(.82,min(1.12,(Window.width or dp(390))/dp(390)))
    def d(self,v):return dp(v)*self.scale
    def f(self,v):return sp(v)*self.scale
    def _on_window_size(self,*_):
        if self._resizing:return
        n=self._get_scale()
        if abs(n-self.scale)<.02:return
        self._resizing=True; self.scale=n; self.navigation.height=self.d(68); self.navigation.padding=self.d(5); self.navigate(self.current_page); self._resizing=False
    def _update_background(self,*_):self.background.pos=self.pos; self.background.size=self.size
    def label(self,text,size=14,bold=False,color=WHITE,align="left"):
        w=Label(text=str(text),font_size=self.f(size),bold=bold,color=color,halign=align,valign="middle",shorten=False)
        w.bind(size=lambda i,v:setattr(i,"text_size",(max(0,v[0]-self.d(4)),v[1]))); return w
    def button(self,text,height=48,accent=False):
        return Button(text=text,size_hint_y=None,height=self.d(height),font_size=self.f(14),bold=True,color=WHITE,background_normal="",background_down="",background_color=PURPLE if accent else CARD2,border=(0,0,0,0))
    def make_card(self,orientation="horizontal",height=70,padding=14):
        return Card(scale=self.scale,orientation=orientation,size_hint_y=None,height=self.d(height),padding=self.d(padding),spacing=self.d(8))
    def clear_page(self):self.page.clear_widgets()
    def scroll_container(self):
        scroll=ScrollView(do_scroll_x=False,do_scroll_y=True,bar_width=self.d(3),scroll_type=["content","bars"])
        box=BoxLayout(orientation="vertical",size_hint=(1,None),padding=(self.d(12),self.d(10),self.d(12),self.d(18)),spacing=self.d(10))
        box.bind(minimum_height=box.setter("height")); scroll.add_widget(box); self.page.add_widget(scroll); return box
    def header(self,title,subtitle=""):
        b=BoxLayout(orientation="vertical",size_hint_y=None,height=self.d(68 if subtitle else 48),spacing=self.d(2))
        b.add_widget(self.label(title,24,True,WHITE,"center"))
        if subtitle:b.add_widget(self.label(subtitle,11,True,PURPLE_LIGHT,"center"))
        return b
    def build_navigation(self):
        nav=BoxLayout(orientation="horizontal",size_hint_y=None,height=self.d(68),padding=(self.d(5),self.d(5)),spacing=self.d(2))
        with nav.canvas.before:Color(*CARD); nav.nav_background=RoundedRectangle(pos=nav.pos,size=nav.size,radius=[self.d(15)])
        nav.bind(pos=lambda i,v:setattr(nav.nav_background,"pos",v),size=lambda i,v:setattr(nav.nav_background,"size",v))
        self.nav_buttons={}; self.nav_icons={}; self.nav_indicators={}
        for name in ("HOME","MARKETS","TRADES","ANALYSIS","SETTINGS"):
            item=BoxLayout(orientation="vertical",spacing=self.d(1),padding=(self.d(2),self.d(4)))
            with item.canvas.before:
                c=Color(*(PURPLE if name==self.current_page else CARD)); shape=RoundedRectangle(pos=item.pos,size=item.size,radius=[self.d(10)])
            item.bind(pos=lambda i,v,s=shape:setattr(s,"pos",v),size=lambda i,v,s=shape:setattr(s,"size",v))
            icon=NavIcon(name,size_hint=(1,.62)); lbl=Label(text=name,size_hint=(1,.38),font_size=self.f(8.5),bold=True,color=PURPLE_LIGHT if name==self.current_page else MUTED,halign="center",valign="middle")
            item.add_widget(icon); item.add_widget(lbl); item.bind(on_touch_down=lambda i,t,p=name:self._nav_touch(i,t,p)); nav.add_widget(item)
            self.nav_buttons[name]=lbl; self.nav_icons[name]=icon; self.nav_indicators[name]=(item,c,shape)
        return nav
    def _nav_touch(self,i,t,p):
        if i.collide_point(*t.pos) and not t.is_mouse_scrolling and t.button is None:self.navigate(p); return True
        return False
    def refresh_navigation(self):
        for name,lbl in self.nav_buttons.items():
            active=name==self.current_page; lbl.color=PURPLE_LIGHT if active else MUTED; self.nav_icons[name].set_color(PURPLE_LIGHT if active else MUTED)
            _,c,_=self.nav_indicators[name]; c.rgba=(PURPLE[0],PURPLE[1],PURPLE[2],.28) if active else CARD
    def navigate(self,page):
        self.current_page=page
        {"HOME":self.show_home,"MARKETS":self.show_markets,"TRADES":self.show_trades,"ANALYSIS":self.show_analysis,"SETTINGS":self.show_settings}.get(page,self.show_home)()
        self.refresh_navigation()

    def show_home(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("GARRY V7","SMC / ICT TRADING BOT"))
        status=self.make_card(height=82); left=BoxLayout(orientation="vertical")
        left.add_widget(self.label("MARKET FEED",10,False,MUTED)); left.add_widget(self.label("FEED STARTED" if self._market_feed_started else "WAITING FOR FEED",14,True,GREEN if self._market_feed_started else ORANGE))
        status.add_widget(left); status.add_widget(self.label("LIVE ORDERS: DISABLED",10,True,MUTED,"right")); box.add_widget(status)
        if self.market_error:box.add_widget(self.label("Feed error: "+self.market_error,10,False,RED))
        if self.paper_error:box.add_widget(self.label("Paper error: "+self.paper_error,10,False,RED))
        market=self.make_card(orientation="vertical",height=160); row=BoxLayout(size_hint_y=None,height=self.d(40),spacing=self.d(6))
        row.add_widget(self.label("MARKET",12,True,MUTED))
        selector=Spinner(text=self.state.symbol,values=APPROVED_SYMBOLS,size_hint_x=None,width=self.d(122),font_size=self.f(12),background_normal="",background_color=CARD2,color=WHITE)
        selector.bind(text=self.change_symbol); row.add_widget(selector); market.add_widget(row)
        p=self._price(self.state.symbol); market.add_widget(self.label(f"{p:,.2f}" if p is not None else "--",25,True,WHITE,"center"))
        market.add_widget(self.label("Delta Exchange India live ticker" if p is not None else "Waiting for fresh public market data",10,False,GREEN if p is not None else MUTED,"center")); box.add_widget(market)
        r=self.paper_result; signal=self.make_card(orientation="vertical",height=110)
        signal.add_widget(self.label("PAPER ANALYSIS",11,True,MUTED)); signal.add_widget(self.label(r.get("signal","WAITING"),22,True,PURPLE_LIGHT,"center"))
        signal.add_widget(self.label(r.get("reason","Start PAPER to analyse public candles."),10,False,MUTED,"center")); box.add_widget(signal)
        controls=self.make_card(height=56,padding=8); start=self.button("START PAPER",42,True); start.disabled=self.paper_session.running; start.bind(on_release=self.start_paper); controls.add_widget(start)
        stop=self.button("STOP PAPER",42); stop.disabled=not self.paper_session.running; stop.bind(on_release=self.stop_paper); controls.add_widget(stop); box.add_widget(controls)
        box.add_widget(self.label("PAPER ONLY • NO EXCHANGE ORDERS",10,True,ORANGE,"center"))
    def change_symbol(self,spinner,value):
        if value not in APPROVED_SYMBOLS:return
        if self.paper_session.running:self.show_notice("STOP PAPER FIRST","Stop PAPER before changing symbol."); spinner.text=self.state.symbol; return
        self.state.symbol=value
        try:self.paper_session.change_symbol(value)
        except (ValueError,RuntimeError):pass
        self.show_home()
    def show_markets(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("MARKETS","DELTA EXCHANGE INDIA • PUBLIC DATA"))
        for symbol in APPROVED_SYMBOLS:
            card=self.make_card(height=68); card.add_widget(self.label(symbol,14,True)); p=self._price(symbol); right=BoxLayout(orientation="vertical")
            right.add_widget(self.label(f"{p:,.2f}" if p is not None else "--",13,True,GREEN if p is not None else ORANGE,"right"))
            right.add_widget(self.label("LIVE" if p is not None else "WAITING / STALE",9,False,MUTED,"right")); card.add_widget(right); box.add_widget(card)
        box.add_widget(self.label("Public prices only. No orders are sent.",10,False,MUTED,"center"))
    def _paper_summary(self):
        engine=getattr(self.paper_session,"engine",None); trader=getattr(engine,"trader",None) if engine else None
        try:return trader.summary() if trader else None
        except Exception:return None
    def show_trades(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("TRADES","PAPER TRADE PERFORMANCE"))
        s=self._paper_summary() or {"total_trades":0,"closed_trades":0,"wins":0,"losses":0,"realized_pnl":0.0}
        closed=int(s.get("closed_trades",0)); wins=int(s.get("wins",0)); pnl=float(s.get("realized_pnl",0))
        for name,value in [("TOTAL TRADES",s.get("total_trades",0)),("WINNING TRADES",wins),("LOSING TRADES",s.get("losses",0)),("WIN RATE",f"{wins/closed*100:.1f}%" if closed else "--"),("NET P&L",f"₹{pnl:,.2f}")]:
            c=self.make_card(height=54); c.add_widget(self.label(name,11,False,MUTED)); c.add_widget(self.label(value,13,True,GREEN if name=="NET P&L" and pnl>=0 else WHITE,"right")); box.add_widget(c)
        box.add_widget(self.label("PAPER RESULTS ONLY • NOT REAL ACCOUNT P&L",10,True,ORANGE,"center"))
    def show_analysis(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("ANALYSIS","SMC / ICT MARKET STRUCTURE")); r=self.paper_result
        for name,value in [("MARKET STRUCTURE","Analysis pending"),("BOS / CHOCH","Analysis pending"),("LIQUIDITY SWEEP","Analysis pending"),("ORDER BLOCK","Analysis pending"),("FVG","Analysis pending"),("IDM","Analysis pending"),("SIGNAL",r.get("signal","WAITING")),("REASON",r.get("reason","Start PAPER to run analysis."))]:
            c=self.make_card(orientation="vertical",height=62); c.add_widget(self.label(name,11,True,MUTED)); c.add_widget(self.label(value,10,False,WHITE)); box.add_widget(c)
        box.add_widget(self.label("Detailed SMC/ICT mapping is not yet individually integrated.",10,False,ORANGE))
    def show_settings(self):
        self.clear_page(); box=self.scroll_container(); box.add_widget(self.header("SETTINGS","GARRY V7 CONFIGURATION"))
        api=self.make_card(orientation="vertical",height=240); api.add_widget(self.label("DELTA API",15,True)); api.add_widget(self.label("Private credentials are not saved in this build.",10,False,MUTED))
        key=TextInput(hint_text="API KEY (not saved)",multiline=False,size_hint_y=None,height=self.d(44),font_size=self.f(13),background_normal="",background_active="",background_color=CARD2,foreground_color=WHITE,hint_text_color=MUTED)
        secret=TextInput(hint_text="API SECRET (not saved)",password=True,multiline=False,size_hint_y=None,height=self.d(44),font_size=self.f(13),background_normal="",background_active="",background_color=CARD2,foreground_color=WHITE,hint_text_color=MUTED)
        api.add_widget(key); api.add_widget(secret); row=BoxLayout(size_hint_y=None,height=self.d(42),spacing=self.d(8))
        save=self.button("SAVE",42,True); save.bind(on_release=self.save_api_notice); row.add_widget(save); test=self.button("TEST",42); test.bind(on_release=self.test_api_notice); row.add_widget(test); api.add_widget(row); box.add_widget(api)
        mode=self.make_card(orientation="vertical",height=205); mode.add_widget(self.label("TRADING MODE",13,True))
        selector=Spinner(text="PAPER",values=("PAPER","LIVE (DISABLED)"),size_hint_y=None,height=self.d(42),font_size=self.f(13),background_normal="",background_color=CARD2,color=WHITE); selector.bind(text=self.select_mode); mode.add_widget(selector)
        mode.add_widget(self.label("LIVE TRADING DISABLED",10,True,ORANGE))
        start=self.button("START PAPER",42,True); start.bind(on_release=self.start_paper); mode.add_widget(start)
        stop=self.button("STOP PAPER",42); stop.bind(on_release=self.stop_paper); mode.add_widget(stop)
        emergency=self.button("EMERGENCY STOP",42); emergency.color=RED; emergency.bind(on_release=self.emergency_stop); mode.add_widget(emergency); box.add_widget(mode)
        box.add_widget(self.label("API credentials are not stored; live orders are disabled.",10,False,MUTED))
