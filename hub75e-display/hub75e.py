from amaranth import *
from amaranth.build import *
from amaranth_boards.icebreaker import *
import enum

hub75e_pmod = [
    Resource("hub75e", 0,
        # rgb
        Subsignal("r0", PinsN("1",  dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("g0", PinsN("2",  dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("b0", PinsN("3",  dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS")),
        
        Subsignal("r1", PinsN("7",  dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("g1", PinsN("8",  dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("b1", PinsN("9",  dir="o", conn=("pmod", 0)), Attrs(IO_STANDARD="SB_LVCMOS")),
        
        # address
        Subsignal("a0", PinsN("1",  dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("a1", PinsN("2",  dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("a2", PinsN("3",  dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("a3", PinsN("4",  dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
        Subsignal("a4", PinsN("10", dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")),
       
        # control pins
        Subsignal("bl", PinsN("7",  dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")), # blank
        Subsignal("la", PinsN("8",  dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")), # latch
        Subsignal("ck", PinsN("9",  dir="o", conn=("pmod", 1)), Attrs(IO_STANDARD="SB_LVCMOS")), # clock
    ),
]


class Hub75E(Elaboratable):

    def elaborate(self, platform):
        class mode(enum.Enum):
            TRANSMIT = 0
            LATCH    = 1
            DISPLAY  = 2

        m = Module()

        stage = Signal(mode)

        # instantiate display from pmod
        disp = platform.request("hub75e")

        address = Signal(5)
        m.d.comb += [
            Cat([disp.a0, disp.a1, disp.a2, disp.a3, disp.a4]).eq(address),
        ]

        freq = 1 # run at full speed
        #freq = int(platform.default_clk_frequency / 100000) # run at 100 kHz
        clock_timer = Signal(range(freq + 1))
        column_counter = Signal(range(64))

        dim_counter = Signal(range(8))
        wait_counter = Signal(8)

        # main clock loop
        with m.If(clock_timer == freq):

            # check the current mode
            with m.Switch(stage):
                with m.Case(mode.TRANSMIT):
                    # enable blanking while transmitting
                    m.d.sync += disp.bl.eq(0)
                    
                    # are we in the zero clock cycle?
                    # (remember everything is upside down!)
                    with m.If(disp.ck):
                        # set pins to some pretty colors
                        # we send the bit with the significance of dim_counter
                        # for that we just shift our color by dim_counter
                        # set pins to value, based on our dim_counter bitshift 
                        m.d.sync += disp.r0.eq(~(column_counter*4) >> dim_counter)
                        m.d.sync += disp.r1.eq(~(column_counter*4) >> dim_counter)

                        m.d.sync += disp.g0.eq((address*4) >> dim_counter)
                        m.d.sync += disp.g1.eq(~(address*8) >> dim_counter)
                    
                        m.d.sync += disp.b0.eq(~(address*4) >> dim_counter)
                        m.d.sync += disp.b1.eq((address*8) >> dim_counter)

                        # enable the clock pin
                        m.d.sync += disp.ck.eq(0)

                    with m.Else():
                        # disable the clock pin
                        m.d.sync += disp.ck.eq(1)

                        # increment the column counter
                        m.d.sync += column_counter.eq(column_counter + 1)

                        # check if we just sent the last bit
                        with m.If(column_counter == 63):
                            # set wait counter according to dim phase
                            # the more significant the bit, the longer we want to wait by a power of two
                            # So we just left-shift 0b00000001 by the significance of the transmitted bit, to get pow(2, dim_counter)
                            m.d.sync += wait_counter.eq(1 << dim_counter)

                            # set next stage to latch
                            m.d.sync += stage.eq(mode.LATCH)

                with m.Case(mode.LATCH):
                    # enable latch
                    m.d.sync += disp.la.eq(0)

                    # go to display stage
                    m.d.sync += stage.eq(mode.DISPLAY)

                with m.Case(mode.DISPLAY):
                    # disable latch
                    m.d.sync += disp.la.eq(1)

                    # disable blanking
                    m.d.sync += disp.bl.eq(1)

                    # was that the last dim wait cycle?
                    with m.If(wait_counter == 0):

                        # if we're in the last dim stage
                        with m.If(dim_counter == 7):
                            # increment address
                            m.d.sync += address.eq(address + 1)
                        
                        # increment dim counter
                        m.d.sync += dim_counter.eq(dim_counter+1)
                    
                        # go back to transmit phase
                        m.d.sync += stage.eq(mode.TRANSMIT)

                    with m.Else():
                        m.d.sync += wait_counter.eq(wait_counter-1)

            # set the clock timer back to 0
            m.d.sync += clock_timer.eq(0)
        with m.Else():
            m.d.sync += clock_timer.eq(clock_timer + 1)

        return m

if __name__ == "__main__":
    # load icebreaker platform
    plat = ICEBreakerPlatform()
    # add hub75e pmod
    plat.add_resources(hub75e_pmod)

    # build and program``
    plat.build(Hub75E(), do_program=True)



