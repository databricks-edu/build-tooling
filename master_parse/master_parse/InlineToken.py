'''
Inline token class, used to configure inline callouts for easy search and replace.

Doctests:

>>> InlineToken(':FOO:', 'https://www.example.org/foo.png').expand()
'<img alt=":FOO:" title=":FOO:" style="vertical-align: text-bottom; position: relative" src="https://www.example.org/foo.png"/>'

>>> InlineToken(':HINT:', 'https://www.example.com/hint.jpg', style='float: left').expand()
'<img alt=":HINT:" title=":HINT:" style="vertical-align: text-bottom; position: relative; float: left" src="https://www.example.com/hint.jpg"/>'

>>> t = InlineToken('X', 'https://www.example.net/x.png')
>>> t.tag
':X:'

>>> t.expand()
'<img alt="X" title="X" style="vertical-align: text-bottom; position: relative" src="https://www.example.net/x.png"/>'

>>> t = InlineToken(':HINT', 'foo.png')
>>> t.tag
':HINT:'

>>> t.title
':HINT'

>>> t = InlineToken('Caution', 'caution.png')
>>> t.tag
':CAUTION:'

>>> t = InlineToken('Caution', 'caution.png', tag=':WARNING:')
>>> t.tag
':WARNING:'

>>> t.expand()
'<img alt="Caution" title="Caution" style="vertical-align: text-bottom; position: relative" src="caution.png"/>'

>>> t = InlineToken('foo bar', 'foobar.jpg')
>>> t.tag
':FOOBAR:'

>>> t = InlineToken(title='Hint', tag=':HINT:', template='**${title}**')
>>> t.expand()
'**Hint**'

>>> tokens = [InlineToken(title='Hint', template="**$title**"),\
              InlineToken(title='Foobar', image="foobar.png"),\
              InlineToken(title='Warning', tag=':WARN:', image="triangle.png")]
>>> content = [":HINT: Don't try to do that.",\
               ":FOOBAR: This is foobar.",\
               "And this is a :HINT: with a :WARNING:."]
>>> print("\\n".join(expand_inline_tokens(tokens, content)))
**Hint** Don't try to do that.
<img alt="Foobar" title="Foobar" style="vertical-align: text-bottom; position: relative" src="foobar.png"/> This is foobar.
And this is a **Hint** with a :WARNING:.
'''

from __future__ import print_function

import re
from string import Template

def expand_inline_tokens(tokens, content):
    '''
    Expand inline tokens in a list of content strings.

    :param tokens    a list of InlineToken objects representing tokens to find and
                     expand
    :param content:  a list of lines to check and expand, if necessary

    :return: A tuple (new_content, needs_sandbox), where new_content is the
             possibly-changed content and needs_sandbox indicates whether or
             not the resulting Markdown should be sandboxed.
    '''
    new_content = []
    needs_sandbox = False
    for line in content:
        new_line = line
        for token in tokens:
            new_line = token.expand_in_string(new_line)
            needs_sandbox = needs_sandbox or ('style=' in new_line)

        new_content.append(new_line)

    return (new_content, needs_sandbox)


class InlineToken(object):
    '''
    Used to represent inline callouts, for easy search and replace.
    '''
    DEFAULT_STYLE = 'vertical-align: text-bottom; position: relative'
    DEFAULT_TEMPLATE = (
        r'''<img alt="${title}" title="${title}" style="${style}" src="${image}"/>'''
    )
    NON_WORDS_RE = re.compile(r'[\W_]+')

    def __init__(self, title, image=None, style=None, template=None, tag=None):
        self.title = title
        self.image = image

        if style:
            self.style = '; '.join([self.DEFAULT_STYLE, style])
        else:
            self.style = self.DEFAULT_STYLE

        self.template = Template(template or self.DEFAULT_TEMPLATE)
        if tag:
            if tag.startswith(':') and tag.endswith(':'):
                self.tag = tag
            elif tag.startswith(':'):
                self.tag = '{0}:'.format(tag)
            elif tag.endswith(':'):
                self.tag = ':{0}'.format(tag)
            else:
                self.tag = ':{0}:'.format(self.tag)
        else:
            self.tag = ':{0}:'.format(self.NON_WORDS_RE.sub('', title).upper())

    def expand(self):
        '''
        Expand the callout (i.e., fill in its template).

        :return: the expanded callout
        '''
        return self.template.substitute(self.__dict__)

    def expand_in_string(self, str):
        '''
        Expand all occurrence of this callout in the supplied string.

        :param str: the string to expand

        :return: the string with any instances of this callout expanded
        '''
        return str.replace(self.tag, self.expand())

    def needs_sandbox(self):
        return 'style=' in self.template

    def clone(self):
        return InlineToken(title=self.title,
                           image=self.image,
                           style=self.style,
                           tag=self.tag)

    def __str__(self):
        return self.tag

    def __repr__(self):
        return (
            "InlineToken('{0}', '{1}', style='{2}', template='{3}', tag='{4}')".format(
                self.title, self.image, self.style, self.template, self.tag
            )
        )


if __name__ == '__main__':
    # Some simple tests
    import doctest
    doctest.testmod()
