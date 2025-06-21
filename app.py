StreamlitAPIException: Slider `min_value` must be less than the `max_value`.

The values were -1 and -1.

────────────────────── Traceback (most recent call last) ───────────────────────

  /home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/scriptru  

  nner/exec_code.py:128 in exec_func_with_error_handling                        

                                                                                

  /home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/scriptru  

  nner/script_runner.py:669 in code_to_exec                                     

                                                                                

  /mount/src/machine-code-dashboard/app.py:128 in <module>                      

                                                                                

    125 │   # Layer slider here                                                 

    126 │   min_l = unique_layers[0] if unique_layers else 0                    

    127 │   max_l = unique_layers[-1] if unique_layers else 0                   

  ❱ 128 │   layer_range = st.slider("Slice Layer Range:", min_l, max_l, (min_l  

    129 │   ticks = layer_ticks(min_l, max_l)                                   

    130 │   st.text(str(ticks))                                                 

    131 │   df_slice = df[(df['Layer']>=layer_range[0])&(df['Layer']<=layer_ra  

                                                                                

  /home/adminuser/venv/lib/python3.13/site-packages/streamlit/runtime/metrics_  

  util.py:443 in wrapped_func                                                   

                                                                                

  /home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/widgets  

  /slider.py:633 in slider                                                      

                                                                                

  /home/adminuser/venv/lib/python3.13/site-packages/streamlit/elements/widgets  

  /slider.py:896 in _slider                                                     

────────────────────────────────────────────────────────────────────────────────

StreamlitAPIException: Slider `min_value` must be less than the `max_value`.

The values were -1 and -1.