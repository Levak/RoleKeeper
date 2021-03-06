#! /usr/bin/env python3

import os

from PIL import Image, ImageFont, ImageDraw
import urllib.request
import io

from locale_s import tr

class Carousel:
    def get_image(self, image_id):
        if image_id in self.images:
            return self.images[image_id]
        else:
            return self.error_img

    def __init__(self, match, bot):
        self.match = match
        self.bot = bot

        # TODO save these ONLY ONCE FOR 1 CUP
        size = (245, 125)
        box = (0, 0, size[0], size[1])

        self.images = {}
        for m in self.match.maps:
            path = 'img/maps/{}.png'.format(m)
            if os.path.exists(path):
                self.images[m] = Image.open(path).resize(size, Image.ANTIALIAS)

        self.block_img = Image.open('img/block.png')
        self.error_img = Image.open('img/replaceme.png').resize(size, Image.ANTIALIAS)
        self.lock_img = Image.open('img/lock.png').resize(size, Image.ANTIALIAS)
        self.turn_img = Image.open('img/turn.png').resize(size, Image.ANTIALIAS)
        self.pick_img = Image.open('img/pick.png').resize(size, Image.ANTIALIAS)
        self.ban_img = Image.open('img/ban.png').resize(size, Image.ANTIALIAS)
        self.banner_img = Image.open('img/banner.png').resize(size, Image.ANTIALIAS)
        self.footer_img = Image.open('img/footer.png')
        self.fnt1 = ImageFont.truetype('WarFace_Regular.ttf', 50)
        self.fnt2 = ImageFont.truetype('WarFace_Regular.ttf', 30)

        self.w, self.h = self.get_image(self.match.maps[0]).size
        self.mode = self.get_image(self.match.maps[0]).mode

        self.fade_img = Image.new(self.mode, (self.w, self.h))
        d2 = ImageDraw.Draw(self.fade_img)
        d2.rectangle([0, 0, self.w, self.h], fill=(0, 0, 0, 180))

        self.teamA_img = None
        if self.match.teamA_icon:
            file = io.BytesIO(urllib.request.urlopen(self.match.teamA_icon).read())
            self.teamA_img = Image.open(file).copy().convert('RGBA')
            self.teamA_img.thumbnail((54, 54), Image.ANTIALIAS)
            file.close()

        self.teamB_img = None
        if self.match.teamB_icon:
            file = io.BytesIO(urllib.request.urlopen(self.match.teamB_icon).read())
            self.teamB_img = Image.open(file).copy().convert('RGBA')
            self.teamB_img.thumbnail((54, 54), Image.ANTIALIAS)
            file.close()

        self.panel_positions = [
            (5,    91),
            (1499, 91),
            (254,  91),
            (1250, 91),
            (503,  91),
            (1001, 91),
            (752,  91),
        ]


    def update_status(self):
        white=(255,255,255,255)
        orange=(255,133,0,255)
        w, h = self.w, self.h
        mode = self.mode

        carousel = Image.new(self.mode, self.footer_img.size)

        carousel = Image.alpha_composite(carousel, self.footer_img)

        match_mode=self.match.mode
        txt_pos = (222, -10)

        d = ImageDraw.Draw(carousel)
        tw, th = d.textsize(self.match.teamA.name, font=self.fnt1)
        d.text(( carousel.size[0] / 2 - tw - txt_pos[0], txt_pos[1]), self.match.teamA.name, font=self.fnt1, fill=white)
        tw, th = d.textsize(self.match.teamB.name, font=self.fnt1)
        d.text(( carousel.size[0] / 2 + txt_pos[0], txt_pos[1]), self.match.teamB.name, font=self.fnt1, fill=white)
        tw, th = d.textsize(match_mode, font=self.fnt2)
        d.text(( (carousel.size[0] - tw) / 2, (50 - th) / 2), match_mode, font=self.fnt2, fill=white)

        if self.teamA_img:
            carousel.paste(self.teamA_img,
                           (int(carousel.size[0] / 2 - txt_pos[0] + 70 - self.teamA_img.size[0]),
                            0,
                            int(carousel.size[0] / 2 - txt_pos[0] + 70),
                            self.teamA_img.size[1]),
                           self.teamA_img)

        if self.teamB_img:
            carousel.paste(self.teamB_img,
                           (int(carousel.size[0] / 2 + txt_pos[0] - 70),
                            0,
                            int(carousel.size[0] / 2 + txt_pos[0] - 70 + self.teamB_img.size[0]),
                            self.teamB_img.size[1]),
                           self.teamB_img)

        num_picked_maps = len(self.match.picked_maps)
        num_banned_maps = len(self.match.banned_maps)
        num_maps = len(self.match.maps)

        teamAi = 0
        teamBi = num_maps - 1
        bani = 0
        picki = 0
        turni = 0

        last_picked = not self.match.last_is_a_pick

        for team, act in self.match.sequence:
            col=white
            if act == 'side':
                if not last_picked:
                    last_picked = True
                    act = 'pick'
                else:
                    continue

            map_id = None

            if act == 'ban' and bani < num_banned_maps:
                map_id = self.match.banned_maps[bani]
                im = self.get_image(map_id)
                im = Image.alpha_composite(im, self.fade_img)
                im = Image.alpha_composite(im, self.ban_img)
                bani += 1

            elif act == 'pick' and picki < num_picked_maps:
                map_id = self.match.picked_maps[picki]
                im = self.get_image(map_id)
                im = Image.alpha_composite(im, self.pick_img)
                picki += 1
                col=orange

            elif turni == num_banned_maps + num_picked_maps:
                im = self.turn_img

            else:
                im = Image.alpha_composite(self.lock_img, self.fade_img)

            if team == self.match.teamA:
                paneli = teamAi
                teamAi += 1
            elif team == self.match.teamB:
                paneli = teamBi
                teamBi -= 1

            ox, oy = 0, 0 #12, 5

            pos = self.panel_positions[turni] if turni < len(self.panel_positions) else (0, 0)

            #carousel.paste(self.block_img,
            #               (pos[0],
            #                pos[1],
            #                pos[0] + self.block_img.size[0],
            #                pos[1] + self.block_img.size[1]))

            if map_id:
                #im = Image.alpha_composite(im, self.banner_img)
                carousel.paste(im, (pos[0] + ox, pos[1] + oy, pos[0] + w + ox, pos[1] + h + oy), im)

                tw, th = d.textsize(tr(map_id), font=self.fnt2)
                d.text(( pos[0] + ox + (w - tw) / 2, pos[1] + oy - 40), tr(map_id), font=self.fnt2, fill=col)
            else:
                carousel.paste(im, (pos[0] + ox, pos[1] + oy, pos[0] + w + ox, pos[1] + h + oy), im)

            turni += 1

        self.carousel = carousel
        return carousel

    def save_status(self):
        c = self.get_status()
        try:
            c.save(os.path.join(self.bot.config['carousel']['save_path'], "status.png"))
        except:
            pass

    def get_status(self):
        cw, ch = self.carousel.size
        #return self.carousel.resize((int(cw/3), int(ch/3)))
        return self.carousel
