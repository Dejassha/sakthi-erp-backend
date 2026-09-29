from rest_framework import serializers
from api.models import *

# Quotation Serial
class QuotationItemSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = QuotationItem
        exclude = ("quotation",)


class QuotationSerializer(serializers.ModelSerializer):
    items = QuotationItemSerializer(many=True)

    class Meta:
        model = Quotation
        fields = "__all__"

    def create(self, validated_data):
        items_data = validated_data.pop("items")

        quotation = Quotation.objects.create(**validated_data)

        for item in items_data:
            QuotationItem.objects.create(quotation=quotation, **item)

        return quotation

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        # Update main quotation fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            # Handle nested items
            existing_items = {item.id: item for item in instance.items.all()}
            updated_item_ids = []

            for item_data in items_data:
                item_id = item_data.get("id")
                if item_id and item_id in existing_items:
                    # Update existing item
                    item = existing_items[item_id]
                    for attr, value in item_data.items():
                        setattr(item, attr, value)
                    item.save()
                    updated_item_ids.append(item_id)
                else:
                    # Create new item
                    new_item = QuotationItem.objects.create(
                        quotation=instance, **item_data
                    )
                    updated_item_ids.append(new_item.id)

            # Delete items that were not in the update payload
            for item_id, item in existing_items.items():
                if item_id not in updated_item_ids:
                    item.delete()

        return instance


class QuotationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = (
            "id",
            "doc_no",
            "doc_date",
            "company_name",
            "mode_of_submission",
            "total_amount",
            "quote_given_by",
            "quote_type",
            "client_remarks",
            "status",
        )


class QuotationNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuotationNote
        fields = "__all__"


