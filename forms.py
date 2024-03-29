import re
import copy
from django.db.models import QuerySet
from django.db.models.manager import Manager
from .html import HtmlHelper


class FormModel(object):
    def __setattr__(self, key, value):
        self.key = value

    def __getattr__(self, item):
        return self.item if hasattr(self, item) else None


class ValidationError(ValueError):
    pass


class FormMeta(type):
    """
    Meta class for extract fields from model
    """

    def __new__(mcs, name, bases, attrs):
        found_fields = dict()

        for k, v in attrs.items():
            if isinstance(v, Field):
                found_fields[k] = v

        attrs['found_fields'] = found_fields

        new_class = super().__new__(mcs, name, bases, attrs)

        parent_fields = {}

        for base in reversed(new_class.__mro__):
            # Collect fields from base class.
            if hasattr(base, 'found_fields'):
                parent_fields.update(base.found_fields)

            # Disable reordered fields.
            for attr, value in base.__dict__.items():
                if value is None and attr in parent_fields:
                    parent_fields.pop(attr)

        new_class.base_fields = parent_fields
        new_class.found_fields = parent_fields

        return new_class


class Field(object):
    """
    Base field class for all derived classes
    """

    def __init__(self, files=None, data=None, instance=None, label=None,
                 attributes=None, attribute=None, form=None,
                 input_type='text', required=False, apply=True, default_value=None, null_if_empty=False,
                 empty_str_if_null=False):
        self.instance = instance
        self.data = data
        self.files = files
        self.form = None
        self._label = label
        self.attribute = attribute

        self.value = None
        self.old_value = None

        self.prefix = ''
        self.form = form
        self.required = required
        self.can_apply = apply
        self.default_value = default_value

        # When value from form is empty (empty string) the property of model while apply becomes None
        self.null_if_empty = null_if_empty
        self.empty_str_if_null = empty_str_if_null

        self.attributes = attributes or dict()

    def apply(self):
        if self.can_apply:
            value = self.value
            setattr(self.instance, self.attribute, value)

    @property
    def dict_value(self):
        return self.value

    def init(self):
        pass

    def set_value(self, value):
        try:
            val = setattr(self.instance, self.attribute, value)
        except:
            val = ''
        return '' if val is None else val

    @property
    def id(self):
        return self.form.prefix + self.attribute

    @property
    def name(self):
        return self.prefix + self.attribute

    @property
    def label(self):
        return self._label or self.attribute

    def create_context(self) -> dict:
        out = {
            'field': self,
        }

        return out

    def get_control_attributes(self):
        return {
            "type": "text",
        }

    def collect_attributes(self, extra_attributes=None):
        attributes = dict()

        attributes.update(self.get_control_attributes())
        attributes.update(extra_attributes or dict())

        if self.attributes:
            attributes.update(self.attributes)

        return attributes

    def render_control(self, extra_attributes=None):
        return HtmlHelper.input(self.name, self.value, self.collect_attributes(extra_attributes))

    def render_label(self):
        return HtmlHelper.tag('label', self.label, {'class': 'form-label'})

    def render_errors(self):
        if self.attribute in self.form.errors:
            return self.form.renderer.render_errors(self, self.form.errors[self.attribute])

        return ''

    def render(self, extra_input_attributes=None):
        return self.form.renderer.render_field(self)

    def load(self, data=None, files=None):
        self.data = data
        self.files = files

        self.set_value_from_data()

    def set_value_from_data(self):
        key = self.prefix + self.attribute
        self.value = self.data[key] if key in self.data else None

        if self.value == '' and self.null_if_empty:
            self.value = None

        if self.value is None and self.empty_str_if_null:
            self.value = ''

    def before_save(self):
        pass

    def after_save(self):
        pass

    def validate(self):
        if self.required and (self.value is None or self.value == ''):
            if self.form is not None:
                error_message = self.form.error_required_message
            else:
                error_message = 'Field %s is required'

            raise ValidationError(error_message % self.label)

    @property
    def js(self):
        return ''

    def fetch(self):
        if hasattr(self.instance, self.attribute):
            self.value = getattr(self.instance, self.attribute)

        if self.value is None and self.default_value is not None:
            self.value = self.default_value

        self.set_old_value()

    def has_changed(self):
        return self.value != self.old_value

    def set_old_value(self):
        self.old_value = self.value


class IntegerField(Field):

    def validate(self):
        try:
            if self.value is not None:
                int(self.value)
        except ValueError:
            if self.form is not None:
                error_message = self.form.error_integer_message
            else:
                error_message = 'Value of %s must be numerical'

            raise ValidationError(error_message % self.label)

    def apply(self):
        try:
            self.value = int(self.value)
            super(IntegerField, self).apply()
        except TypeError:
            pass

    # def apply(self):
    #     try:
    #         setattr(self.instance, self.attribute, int(self.value))
    #     except ValueError:
    #         pass


class InputField(Field):
    def __init__(self, *args, input_type='text', **kwargs):
        self.input_type = input_type
        super(InputField, self).__init__(*args, **kwargs)

    def collect_attributes(self, extra_attributes=None):
        attributes = super(InputField, self).collect_attributes(extra_attributes)
        attributes['type'] = self.input_type
        return attributes


class NestedFormField(Field):
    def __init__(self, form_class=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.form_class = form_class
        self.nested_form = None

    @property
    def dict_value(self):
        return self.nested_form.to_dict()

    def fetch(self):
        """ Fetch nested object from instance """
        f = self.form.instance._meta.get_field(self.attribute)

        if hasattr(self.instance, f.name):
            instance = getattr(self.instance, f.name)

            if isinstance(instance, QuerySet):
                try:
                    instance = instance.get()
                except f.related_model.DoesNotExist:
                    instance = f.related_model()
            elif isinstance(instance, Manager):
                instance = instance.first()
                if instance is None:
                    instance = f.related_model()
        else:
            instance = f.related_model()

        # create nested form for rendering
        self.nested_form = self.form_class(
            prefix=self.prefix + '-',
            instance=instance,
            parent_form=self.form
        )

    def render_control(self, extra_attributes=None):
        return HtmlHelper.tag('div', self.nested_form.render(),
                              {"style": "border-left: 4px solid #eee; padding-left: 20px;"})

    def apply(self):
        pass

    def load(self, data=None, files=None):
        self.nested_form.load(data, files)

    def after_save(self):
        self.set_relative_fields(self.nested_form.instance)
        self.nested_form.save()

    def set_relative_fields(self, instance):
        f = self.form.instance._meta.get_field(self.attribute)
        setattr(instance, f.field.name, self.form.instance)

    @property
    def js(self):
        return self.nested_form.js


class GenericNestedForm(NestedFormField):
    """
    Many to one relation. This field store instance that bind to self.instance (current host model)
    Set related column to current instance
    """

    def __init__(self, related_field='item', *args, **kwargs):
        super(GenericNestedForm, self).__init__(*args, **kwargs)
        self.related_field = related_field

    def set_relative_fields(self, instance):
        setattr(instance, self.related_field, self.instance)


class ColorField(Field):
    """
    Field just for testing. Js is work
    """

    @property
    def js(self):
        return "$(el).css('background', 'black');"


class BootstrapFormRenderer(object):
    form_group_class = "form-group"
    form_error_class = 'form-error'

    def __init__(self, form):
        self.form = form

    def render_errors(self, field, errors):
        return HtmlHelper.tag('div', ', '.join(errors), {'class': self.form_error_class})

    def render_form(self, field):
        out = list()

        for name, field in self.form.fields.items():
            out.append(field.render())

        return ''.join(out)

    def render_field(self, field):

        if isinstance(field, HiddenIdField):
            return field.render_control()

        extra_attributes = {
            'class': 'form-control',
            'id': field.id
        }

        return '<div class="%s">%s%s%s</div>' % (
            self.form_group_class,
            field.render_label(),
            field.render_control(extra_attributes=extra_attributes),
            field.render_errors()
        )


class TableFormRenderer(BootstrapFormRenderer):

    def render_field(self, field):
        if isinstance(field, HiddenIdField):
            return field.render_control()

        extra_attributes = {
            'class': 'form-control',
            'id': field.id
        }

        return '<td>%s%s%s</td>' % (
            field.render_label(),
            field.render_control(extra_attributes=extra_attributes),
            field.render_errors())


class Form(object, metaclass=FormMeta):
    """
    Main form class
    """

    error_required_message = 'Field %s is required'

    def __init__(self, instance=None, data=None, files=None, parent_form=None, fields=None, prefix='', template=None,
                 renderer_class=BootstrapFormRenderer):
        self.template = template if template is not None else 'forms/form.html'

        self.instance = instance
        self.data = data or list()
        self.files = files or list()
        self.parent_form = parent_form
        self.renderer = renderer_class(self)

        self.prefix = prefix

        # self.fields = fields or list()
        self.fields_config = fields
        self.errors = dict()
        self.fields = dict()

        # initialize fields
        for name, field in self.found_fields.items():
            self.fields[name] = copy.deepcopy(field)
            self.fields[name].form = self
            self.fields[name].attribute = name
            self.fields[name].instance = self.instance
            self.fields[name].prefix = self.prefix
            self.fields[name].fetch()

    def init(self):
        pass

    def load(self, data=None, files=None):
        self.data = data
        self.files = files

        for name, field in self.fields.items():
            field.load(data, files)

    def normalize_field_config(self, config) -> list:

        out_fields = []
        field_description = dict()

        for f in config:
            if isinstance(f, dict):
                field_description = f

            if isinstance(f, str):
                field_description = {
                    'attribute': f,
                    'classname': Field,
                }

            if 'fields' in field_description:
                field_description['fields'] = self.normalize_field_config(
                    field_description['fields'])

            if 'classname' not in field_description:
                field_description['classname'] = Field

            out_fields.append(field_description)

        return out_fields

    def save(self):
        for _, f in self.fields.items():
            f.before_save()

        self.before_save()

        for _, f in self.fields.items():
            f.apply()

        self.after_apply()

        self.instance.save()

        for _, f in self.fields.items():
            f.after_save()

        return True

    def render(self):
        return self.renderer.render_form(self)

    def add_field_error(self, field, error):
        if field not in self.errors:
            self.errors[field] = list()

        self.errors[field].append(error)

    def is_valid(self):
        valid = True

        for _, f in self.fields.items():
            try:
                f.validate()
            except ValidationError as err:
                valid = False
                self.add_field_error(f.name, str(err))

        self.custom_validation()

        return valid and len(self.errors.items()) == 0

    def custom_validation(self):
        pass

    def __str__(self):
        return self.render()

    @property
    def js(self):
        fields_js = list()

        for _, f in self.fields.items():
            fields_js.append("(function (el) { %s })($('#%s'));" % (f.js, f.id))

        return '''
            $(document).ready(function () {
                %s
            });
        ''' % ("\n".join(fields_js))

    def before_save(self):
        pass

    def after_apply(self):
        pass

    def after_save(self):
        pass

    @property
    def values(self):
        out = dict()
        for k, f in self.fields.items():
            out[k] = f.value

        return out

    def to_dict(self):
        return {field_name: field.dict_value for field_name, field in self.fields.items()}


class HiddenIdField(Field):
    def apply(self):
        pass

    def render_label(self):
        pass

    def render_errors(self):
        pass

    def render_control(self, extra_attributes=None):
        return HtmlHelper.tag('input', '', {
            "type": "hidden",
            "value": self.value,
            "name": self.name
        })


class SelectField(Field):
    def __init__(self, options=None, *args, **kwargs):
        if options is not None:
            self.options = options
        else:
            self.options = list()

        super(SelectField, self).__init__(*args, **kwargs)

        self.template = 'forms/select.html'

    def render_control(self, extra_attributes=None):
        attributes = self.attributes or dict()
        attributes.update(extra_attributes or dict())

        return HtmlHelper.select(self.name, self.value, self.options, attributes)


class UrlField(Field):
    pass


class BooleanField(Field):
    def __init__(self, *args, **kwargs):
        super(BooleanField, self).__init__(*args, **kwargs)
        self.template = 'forms/boolean-field.html'


class CheckBoxListField(Field):
    def __init__(self, *args, options=None, **kwargs):
        self.options = options or list()
        super(CheckBoxListField, self).__init__(*args, **kwargs)

    # def create_context(self):
    #     context = super(CheckBoxListField, self).create_context()
    #     f = self.instance._meta.get_field(self.attribute)
    #     related_model = f.related_model()
    #     variants = related_model.__class__.objects.all()
    #     variants = [{'label': v.name, 'value': v.id} for v in variants]
    #
    #     checked = []
    #
    #     context.update({
    #         'checkboxes': variants,
    #         'checked': checked,
    #     })
    #
    #     return context

    def get_options(self):
        return self.options

    # def load(self, data=None, files=None):
    #     pass

    def render_control(self, extra_attributes=None):
        options = list()

        attr_name = self.name

        for id, name in self.get_options():
            input = HtmlHelper.tag('input', '', {
                "type": "checkbox",
                "value": id,
                "name": attr_name,
                "checked": id in self.value
            }) + ' ' + str(name)
            options.append(HtmlHelper.tag('li', input))

        return HtmlHelper.tag('ul', ''.join(options))


class ManyToManyCheckBoxListField(CheckBoxListField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.local_field = None
        self.related_field = None
        self.remote_model_id_field = None

    def fetch(self):
        self.local_field = self.instance._meta.get_field(self.attribute)
        self.remote_field = self.local_field.remote_field

        self.remote_model_id_field = self.local_field.target_field.name.split('.')[-1]

        if self.options is True:
            all_related_class_models = self.local_field.related_model.objects.all()
            self.options = [
                (
                    getattr(a, self.remote_model_id_field),
                    getattr(a, self.remote_model_id_field)
                )
                for a in all_related_class_models
            ]

        value = []

        if self.instance.id:
            for a in getattr(self.instance, self.attribute).all():
                value.append(getattr(a, self.remote_model_id_field))

        self.value = value

    def apply(self):
        pass

    def after_save(self):
        categories = self.local_field.related_model.objects.filter(id__in=self.value)
        getattr(self.instance, self.attribute).set(categories)

    def set_value_from_data(self):
        key = self.prefix + self.attribute
        self.value = self.data[key] if key in self.data else None
        if self.value is None:
            self.value = list()


class CheckBoxField(Field):
    def get_control_attributes(self):
        return {
            "type": "checkbox",
            "name": self.name
        }

    def apply(self):
        checked = self.value == '1'
        setattr(self.instance, self.attribute, checked)

    def render_control(self, extra_attributes=None):
        attributes = self.collect_attributes()

        is_checked = True if self.value is True or self.value == 1 or self.value == '1' else False
        attributes['checked'] = is_checked
        attributes['value'] = 1

        checked = HtmlHelper.tag('input', '', attributes)

        attributes = attributes.copy()
        attributes['type'] = 'hidden'
        attributes['value'] = 0
        del attributes['checked']
        hidden = HtmlHelper.tag('input', '', attributes)

        return hidden + checked


class FormsetField(Field):

    def __init__(self, form_class=None, text_delete='Delete row', text_add='Add new row', *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.hidden_form = None
        self.forms = dict()
        self.form_class = form_class

        self.text_delete = text_delete
        self.text_add = text_add

    def set_relative_fields(self, instance):
        f = self.form.instance._meta.get_field(self.attribute)
        setattr(instance, f.field.name, self.form.instance)

    def fetch(self):
        hidden_form = self.create_child_form(
            '__index__', self.create_new_instance())
        self.hidden_form = hidden_form

        self.init_forms()

    def get_attr_value(self):
        if self.instance is not None and self.instance.id is not None:
            attr_value = getattr(self.instance, self.attribute).all()
        else:
            attr_value = []

        return attr_value

    def render_control(self, extra_attributes=None):
        forms = [HtmlHelper.tag('div', f.render())
                 for _, f in self.forms.items()]

        hidden_form = HtmlHelper.tag('div', self.hidden_form.render())

        buttons = HtmlHelper.tag('a', self.text_add, {
            'class': 'add btn btn-success btn-sm mt-2', 'href': '#'})
        container = HtmlHelper.tag('div', ''.join(forms), {
            'class': 'container'})
        hidden = HtmlHelper.tag('div', hidden_form, {'class': 'hidden'})

        return HtmlHelper.tag('div', container + hidden + buttons,
                              self.collect_attributes({'id': self.id}))

    def get_max_index(self):
        form_indexes = [int(a) for a in self.forms.keys()]
        return max(form_indexes) + 1 if len(form_indexes) > 0 else 0

    def collect_form_js(self):
        forms_js = list()
        for _, f in self.forms.items():
            forms_js.append(f.js)

        return ''.join(forms_js)

    def collect_fields_js(self):
        fields_js = list()
        for _, f in self.hidden_form.fields.items():
            fields_js.append(
                "(function (el) { %s })($('#%s'.replace('__index__', i)));" % (f.js, f.id))
        return ''.join(fields_js)

    @property
    def js(self):
        return '''
            let i = {max_index};
            let container = $(el).find('> .container')
            let button = $(el).find('> .add');
            let hidden = $(el).find('> .hidden');
            
            {forms_js}
            
            hidden.hide()
            
            container.find('> *').each(function(indx, el){{
                let delBtn = $('<button type="button" class="btn btn-sm btn-danger">{text_delete}</button>');
                
                delBtn.on('click', () => {{
                    el.remove();
                }})
                
                $(el).append(delBtn);
            }})
            
            button.on('click', function(e) {{
                e.preventDefault();
                
                let newForm = hidden.find(' > div ').clone();
                
                newForm.find('[name], [id]').each((index, item) => {{
                    ['name', 'id'].forEach(attr => {{
                        if($(item).attr(attr)){{
                            let newAttr = $(item).attr(attr).replace(/__index__/, i);
                            console.log('was value', $(item).attr(attr), 'replace with', newAttr)
                            
                            $(item).attr(attr, newAttr)
                        }}
                    }})
                }})
                
                let delBtn = $('<button type="button" class="btn btn-sm btn-danger">{text_delete}</button>');
                
                delBtn.on('click', () => {{
                    newForm.remove();
                }})
                
                newForm.append(delBtn);
                container.append(newForm);
                
                {init_nested_field}
                
                console.log('index', i)
                
                i++;
            }})
        '''.format(id=self.id,
                   max_index=self.get_max_index(),
                   init_nested_field=self.collect_fields_js(),
                   forms_js=self.collect_form_js(),
                   text_delete=self.text_delete,
                   text_add=self.text_add
                   )

    def init_forms(self):
        attr_value = self.get_attr_value()

        i = 0
        for a in attr_value:
            self.forms[str(i)] = self.create_child_form(i, a)
            i += 1

    def create_new_instance(self):
        field = self.instance._meta.get_field(self.attribute)

        instance = field.related_model()
        return instance

    def load(self, data=None, files=None):
        self.data = data
        self.files = files

        prefix_pattern = self.nested_form_prefix('__index__')
        pattern = re.escape(prefix_pattern)
        pattern = '^' + pattern.replace('__index__', '(\\d+)')

        forms_indexes = []

        for key, value in data.items():
            groups = re.match(pattern, key)
            if groups is not None:
                index = groups.group(1)
                if index not in forms_indexes:
                    forms_indexes.append(index)

        new_forms = dict()

        for index in forms_indexes:
            str_index = str(index)

            if str_index == "__index__":
                continue

            try:
                new_forms[str_index] = self.forms[str_index]
                new_forms[str_index].load(data, files)
            except KeyError:
                new_forms[str_index] = self.create_child_form(
                    index, self.create_new_instance())
                new_forms[str_index].load(data, files)

        self.forms = new_forms

    def nested_form_prefix(self, index):
        return self.form.prefix + self.attribute + '-' + str(index) + '-'

    def create_child_form(self, index, instance=None):
        form_prefix = self.nested_form_prefix(index)
        form_class = self.form_class
        new_form = form_class(
            instance=instance, prefix=form_prefix, parent_form=self.form)
        return new_form

    def after_save(self):
        attr_value = self.get_attr_value()
        attr_value = [a for a in attr_value]

        added = []

        for i, form in self.forms.items():
            self.set_relative_fields(form.instance)
            form.save()

            added.append(form.instance)

        [a.delete() for a in attr_value if a not in added]

    def apply(self):
        pass


class TableFormsetField(FormsetField):
    def render_control(self, extra_attributes=None):
        forms = [HtmlHelper.tag('tr', f.render())
                 for _, f in self.forms.items()]

        hidden_form = HtmlHelper.tag('tbody', HtmlHelper.tag('tr', self.hidden_form.render()))

        buttons = HtmlHelper.tag('a', self.text_add, {
            'class': 'add', 'href': '#'})

        container = HtmlHelper.tag('table', ''.join(forms), {
            'class': 'container'})

        hidden = HtmlHelper.tag('table', hidden_form, {'class': 'hidden'})

        return HtmlHelper.tag('div', container + hidden + buttons, {'id': self.id})

    @property
    def js(self):
        return '''
                let i = {max_index};
                let container = $('#{id} > .container')
                let button = $('#{id} > .add');
                let hidden = $('#{id} > .hidden');

                {forms_js}

                hidden.hide()

                container.find('> *').each(function(indx, el){{
                    let delBtn = $('<button type="button" class="btn btn-sm btn-danger">{text_delete}</button>');

                    delBtn.on('click', () => {{
                        el.remove();
                    }})

                    $(el).append(delBtn);
                }})

                button.on('click', function(e) {{
                    e.preventDefault();

                    let newForm = hidden.find(' > tbody > tr ').clone();

                    newForm.find('[name], [id]').each((index, item) => {{
                        ['name', 'id'].forEach(attr => {{
                            if($(item).attr(attr)){{
                                $(item).attr(attr, $(item).attr(attr).replace(/__index__/g, i))
                            }}
                        }})
                    }})

                    let delBtn = $('<button type="button" class="btn btn-sm btn-danger align-end">{text_delete}</button>');

                    delBtn.on('click', () => {{
                        newForm.remove();
                    }})

                    newForm.append(delBtn);
                    container.append(newForm);

                    {init_nested_field}

                    i++;
                }})
            '''.format(id=self.id,
                       max_index=self.get_max_index(),
                       init_nested_field=self.collect_fields_js(),
                       forms_js=self.collect_form_js(),
                       text_delete=self.text_delete,
                       text_add=self.text_add
                       )

    def create_child_form(self, index, instance=None):
        form_prefix = self.nested_form_prefix(index)
        form_class = self.form_class
        new_form = form_class(instance=instance, prefix=form_prefix, parent_form=self.form,
                              renderer_class=TableFormRenderer)
        return new_form


class ManyToOneField(FormsetField):
    pass


class JsField(Field):
    @property
    def js(self):
        return 'el.css("background", "yellow");'


class TextAreaField(Field):
    def render_control(self, extra_attributes=None):
        return HtmlHelper.textarea(self.name, self.value, self.collect_attributes(extra_attributes))


class FileField(Field):

    def set_value_from_data(self):
        key = self.prefix + self.attribute
        self.value = self.files[key] if key in self.files else None

    def apply(self):
        if self.can_apply and self.value:
            setattr(self.instance, self.attribute, self.value)

    def render_existing_value(self):
        f = self.value.url if self.value else ''
        return HtmlHelper.tag('a', f, {'href': f, 'target': '_blank'})

    def render_control(self, extra_attributes=None):
        attributes = self.attributes or dict()
        attributes.update(extra_attributes or dict())
        attributes['type'] = 'file'

        render_input = HtmlHelper.input(self.name, self.value, attributes)

        wrapper = HtmlHelper.tag('div', self.render_existing_value() + render_input)

        return wrapper


class EditorField(TextAreaField):
    @property
    def js(self):
        return "CKEDITOR.replace(el[0]);"


def generate_form_class(fields, base_class=Form):
    """Create form class dynamically from fields"""
    return type('_Form', (base_class,), fields)


class ReadOnlyField(Field):
    def apply(self):
        pass

    def load(self, data=None, files=None):
        pass


class TextField(InputField):
    def __init__(self, *args,
                 min_length=None,
                 max_length=None,
                 **kwargs):

        self.min_length = min_length
        self.max_length = max_length

        self.min_length_error_message = 'Minimum length of %s is %d'
        self.max_length_error_message = 'Maximum length of %s is %d'

        kwargs['input_type'] = 'text'
        super().__init__(*args, **kwargs)

    def validate(self):
        super(TextField, self).validate()

        if self.min_length and len(self.value) < self.min_length:
            raise ValidationError(self.min_length_error_message % (self.label, self.min_length))

        if self.max_length and len(self.value) < self.max_length:
            raise ValidationError(self.max_length_error_message % (self.label, self.max_length))
