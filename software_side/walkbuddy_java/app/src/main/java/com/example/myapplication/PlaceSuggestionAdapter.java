package com.example.myapplication;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.TextView;

import java.util.ArrayList;
import java.util.List;

public class PlaceSuggestionAdapter extends ArrayAdapter<String> {
    private Context context;
    private List<String> suggestions;
    private LayoutInflater inflater;

    public PlaceSuggestionAdapter(Context context) {
        super(context, android.R.layout.simple_list_item_2, new ArrayList<>());
        this.context = context;
        this.suggestions = new ArrayList<>();
        this.inflater = LayoutInflater.from(context);
    }

    public void updateSuggestions(List<String> newSuggestions) {
        this.suggestions.clear();
        this.suggestions.addAll(newSuggestions);
        clear();
        addAll(newSuggestions);
        notifyDataSetChanged();
    }

    @Override
    public View getView(int position, View convertView, ViewGroup parent) {
        ViewHolder holder;
        
        if (convertView == null) {
            convertView = inflater.inflate(android.R.layout.simple_list_item_2, parent, false);
            holder = new ViewHolder();
            holder.primaryText = convertView.findViewById(android.R.id.text1);
            holder.secondaryText = convertView.findViewById(android.R.id.text2);
            convertView.setTag(holder);
        } else {
            holder = (ViewHolder) convertView.getTag();
        }

        String suggestion = getItem(position);
        
        // Split the suggestion into primary and secondary parts
        if (suggestion != null && suggestion.contains(" - ")) {
            String[] parts = suggestion.split(" - ", 2);
            holder.primaryText.setText(parts[0]);
            holder.secondaryText.setText(parts[1]);
        } else {
            holder.primaryText.setText(suggestion != null ? suggestion : "");
            holder.secondaryText.setText("");
        }

        // Style the text
        holder.primaryText.setTextColor(context.getResources().getColor(android.R.color.black));
        holder.primaryText.setTextSize(16);
        holder.secondaryText.setTextColor(context.getResources().getColor(android.R.color.darker_gray));
        holder.secondaryText.setTextSize(14);

        return convertView;
    }

    private static class ViewHolder {
        TextView primaryText;
        TextView secondaryText;
    }
}
