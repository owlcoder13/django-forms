from xml.sax.saxutils import escape, unescape


class HtmlHelper(object):
    auto_close_tags = [
        'br',
        'img',
        'meta',
        'input',
    ]

    @classmethod
    def escape(cls, expression):
        if expression is None:
            return ''

        expression = str(expression)

        if not isinstance(expression, str):
            print(expression)
            raise Exception("expression must be string")

        return escape(expression)

    @classmethod
    def tag(cls, tag, content=None, attributes=None):
        attributes = attributes or dict()
        joined_attributes = list()

        for key, attr in attributes.items():
            if attr is True:
                case = '%s' % key
            elif attr is False:
                continue
            else:
                case = '%s="%s"' % (key, cls.escape(attr))
            joined_attributes.append(case)

        if len(joined_attributes) > 0:
            joined_attributes = ' ' + ' '.join(joined_attributes)
        else:
            joined_attributes = ''

        if tag in cls.auto_close_tags:
            return "<%s%s/>" % (tag, joined_attributes)
        else:
            content = content if content is not None else ''
            return "<%s%s>%s</%s>" % (tag, joined_attributes, content, tag)

    @classmethod
    def div(cls, content=None, attributes=None):
        return cls.tag('div', content, attributes)

    @classmethod
    def link(cls, label=None, href='#', attributes=None):
        attributes = attributes or dict()
        attributes['href'] = href
        return cls.tag('a', label, attributes)

    @classmethod
    def input(cls, name=None, value=None, attributes=None):
        attributes = attributes or dict()

        attributes.update({
            "name": name,
            "value": value
        })

        return cls.tag('input', None, attributes)

    @classmethod
    def textarea(cls, name=None, value=None, attributes=None):
        attributes = attributes or dict()

        attributes.update({
            "name": name,
        })

        return cls.tag('textarea', value, attributes)

    @classmethod
    def select(cls, name=None, value=None, options=None, attributes=None):
        if options is None:
            options = list()

        render_options = []

        for key, text in options:
            option = HtmlHelper.tag('option', text, {
                "value": key, "selected": value == key
            })
            render_options.append(option)

        attributes = attributes or dict()

        attributes.update({
            "name": name,
        })

        return cls.tag('select', ''.join(render_options), attributes)

    @classmethod
    def img(cls, src, alt='', options=None):
        options = options or dict()
        options.update({'src': src, 'alt': alt})
        return cls.tag('img', None, options)
