import urwid
import urwid.curses_display
import click

from pcvsrt.helpers import log

@click.command("gui", short_help="Gui-based PCVS")
@click.pass_context
def gui(ctx):
    main()


def exit_properly(k):
    if k in ('q', 'Q'):
        raise urwid.ExitMainLoop()


color_palette = [
    ('banner', 'dark red', 'light gray'),
    ('streak', 'black', 'light gray'),
    ('bg', 'black', 'dark gray')

]

def main():
    txt = urwid.Text(('banner', u'\nParallel Computing -- Validation Suite\n\nWork in Progress, stay tuned!'), align='center')
    fill = urwid.Filler(txt, 'middle')
    loop = urwid.MainLoop(fill,
                          unhandled_input=exit_properly,
                          screen=urwid.curses_display.Screen()
                        )
    loop.run()