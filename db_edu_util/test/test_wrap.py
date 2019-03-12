from db_edu_util import EnhancedTextWrapper, strip_margin

def test_wrap():
    e = EnhancedTextWrapper(width=40)
    text = ('Lorem ipsum dolor sit amet, consectetur adipiscing elit, ' +
            'sed do eiusmod tempor incididunt ut labore et dolore magna ' +
            'aliqua. Ut enim ad minim veniam, quis nostrud exercitation ' +
            'ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis ' +
            'aute irure dolor in reprehenderit in voluptate velit esse ' +
            'cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat ' +
            'cupidatat non proident, sunt in culpa qui officia deserunt ' +
            'mollit anim id est laborum.')
    assert e.fill(text) == strip_margin(
        '''|Lorem ipsum dolor sit amet, consectetur
           |adipiscing elit, sed do eiusmod tempor
           |incididunt ut labore et dolore magna
           |aliqua. Ut enim ad minim veniam, quis
           |nostrud exercitation ullamco laboris
           |nisi ut aliquip ex ea commodo consequat.
           |Duis aute irure dolor in reprehenderit
           |in voluptate velit esse cillum dolore eu
           |fugiat nulla pariatur. Excepteur sint
           |occaecat cupidatat non proident, sunt in
           |culpa qui officia deserunt mollit anim
           |id est laborum.''')

    e = EnhancedTextWrapper(width=70)
    assert e.fill(text) == strip_margin(
        '''|Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
           |eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad
           |minim veniam, quis nostrud exercitation ullamco laboris nisi ut
           |aliquip ex ea commodo consequat. Duis aute irure dolor in
           |reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
           |pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
           |culpa qui officia deserunt mollit anim id est laborum.''')

    e = EnhancedTextWrapper(width=70, subsequent_indent='   ')
    assert e.fill(text) == strip_margin(
      '''|Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
         |   eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim
         |   ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut
         |   aliquip ex ea commodo consequat. Duis aute irure dolor in
         |   reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla
         |   pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
         |   culpa qui officia deserunt mollit anim id est laborum.''')

    e = EnhancedTextWrapper(width=70)
    text = ('Lorem ipsum dolor sit amet,\nconsectetur adipiscing elit, ' +
            'sed do eiusmod tempor\nincididunt ut labore et dolore magna ' +
            'aliqua. Ut enim ad minim veniam, quis nostrud exercitation')
    assert e.fill(text) == strip_margin(
        '''|Lorem ipsum dolor sit amet,
           |consectetur adipiscing elit, sed do eiusmod tempor
           |incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam,
           |quis nostrud exercitation''')

