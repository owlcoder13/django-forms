import os, sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from forms import forms


#
# class JobForm(Form):
#     name = Field()
#
#
# class SimpleForm(Form):
#     name = Field()
#     description = TextAreaField()
#     jobs = FormsetField(form=JobForm)
#
#
# class DataObject(object):
#     def __init__(self, name=None, description=None):
#         self.name = name
#         self.description = description
#
#     def save(self):
#         print('I saved properties :)')
#
#     def __str__(self):
#         return '%s:%s' % (self.name, self.description)
#
#
# item = DataObject(name='Misha', description="Best programmer ever")
#
# form = SimpleForm(instance=item)
# print(form.render())
# print(item)
# form.load(data={'name': 'Misha2', 'description': 'new description'})
# print(form.render())
# print(item)
# form.save()
# print(form.render())
# print(item)

class Form1(forms.Form):
    name = forms.Field()
    description = forms.TextAreaField()


model = forms.FormModel()
form = Form1(instance=model)
