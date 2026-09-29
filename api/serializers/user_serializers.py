from rest_framework import serializers
from api.models import *

class AdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = Admin
        fields = "__all__"


class All_UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = All_User
        fields = "__all__"


